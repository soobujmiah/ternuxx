#!/usr/bin/env python3
"""Run bounded, guarded Native Termux inference qualification calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TX = ROOT / "tx"
BACKENDS = {"cpu", "vulkan", "npu"}


@dataclass(frozen=True)
class QualificationCase:
    case_id: str
    prompt: str
    expression: str
    answer: str


PROMPT_SUITE_ID = "arithmetic-operators-v1"
QUALIFICATION_CASES = (
    QualificationCase("addition-2-plus-2-v1", "2 + 2? Reply with one digit.", r"2\s*\+\s*2", "4"),
    QualificationCase("subtraction-9-minus-4-v1", "What is 9 - 4? Answer with one digit.", r"9\s*-\s*4", "5"),
    QualificationCase("multiplication-3-times-2-v1", "3 * 2? Reply with one digit.", r"3\s*\*\s*2", "6"),
)


def qualification_case_for_run(index: int) -> QualificationCase:
    if index < 1:
        raise ValueError("run index must be positive")
    return QUALIFICATION_CASES[(index - 1) % len(QUALIFICATION_CASES)]


def _answer_pattern(case: QualificationCase) -> re.Pattern[str]:
    expression = rf"(?:{case.expression}\s*=\s*)?"
    return re.compile(expression + re.escape(case.answer) + r"[.!]?\Z")


def read_temperatures(root: Path = Path("/sys/class/thermal")) -> dict[str, float]:
    groups: dict[str, list[float]] = {name: [] for name in ("cpu", "gpu", "htp", "battery", "socd")}
    try:
        zones = root.glob("thermal_zone*")
        for zone in zones:
            try:
                name = (zone / "type").read_text(encoding="utf-8").strip().lower()
                raw = float((zone / "temp").read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            value = raw / 1000 if abs(raw) >= 1000 else raw
            if not 0 < value < 150:
                continue
            if name == "cpu_therm" or name.startswith(("cpu-", "cpuss-")):
                groups["cpu"].append(value)
            elif name.startswith("gpu-"):
                groups["gpu"].append(value)
            elif name.startswith(("nsphvx-", "nsphmx-")):
                groups["htp"].append(value)
            elif name in {"battery", "batt_therm"}:
                groups["battery"].append(value)
            elif name == "socd":
                groups["socd"].append(value)
    except OSError:
        pass
    return {name: round(max(values), 2) for name, values in groups.items() if values}


def read_memavailable_kib(path: Path = Path("/proc/meminfo")) -> int | None:
    try:
        for line in path.read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def resource_violations(snapshot: dict[str, float | int | None], limits: dict[str, float],
                        minimum_mem_kib: int) -> list[str]:
    issues = [f"{name}={snapshot[name]} C reached guard {limit} C"
              for name, limit in limits.items()
              if snapshot.get(name) is not None and float(snapshot[name]) >= limit]
    available = snapshot.get("memavailable_kib")
    if available is None:
        issues.append("MemAvailable could not be read")
    elif int(available) < minimum_mem_kib:
        issues.append(f"MemAvailable={int(available) // 1024} MiB is below guard {minimum_mem_kib // 1024} MiB")
    return issues


def parse_result(stdout: str, backend: str,
                 case: QualificationCase = QUALIFICATION_CASES[0]) -> tuple[bool, dict[str, object] | None, str | None]:
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return False, None, "tx ai run returned invalid JSON"
    if not isinstance(envelope, dict) or envelope.get("ok") is not True:
        error = envelope.get("error", {}) if isinstance(envelope, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        return False, None, str(message or "tx ai run failed")
    data = envelope.get("data")
    if not isinstance(data, dict):
        return False, None, "tx ai run returned no result data"
    expected = {"cpu": "CPU", "vulkan": "Vulkan", "npu": "Hexagon HTP"}[backend]
    if data.get("backend") != expected:
        return False, data, f"expected backend {expected}; got {data.get('backend')}"
    if backend == "vulkan":
        delegated, total = data.get("gpu_layers"), data.get("gpu_total_layers")
        if type(delegated) is not int or type(total) is not int or delegated <= 0 or delegated != total:
            return False, data, "Vulkan result did not prove complete positive GPU-layer offload"
    elif backend == "npu":
        delegated, total = data.get("npu_layers"), data.get("total_layers")
        if (type(delegated) is not int or type(total) is not int or delegated <= 0 or delegated != total
                or data.get("silent_fallback") is not False):
            return False, data, "HTP result did not prove complete offload with fallback disabled"
    elif type(data.get("gpu_layers")) is not int or data["gpu_layers"] != 0:
        return False, data, "CPU result did not report integer zero GPU layers"
    if not isinstance(data.get("output"), str) or not data["output"].strip():
        return False, data, "inference returned empty output"
    if not _answer_pattern(case).fullmatch(data["output"].strip()):
        return False, data, f"inference did not match the expected answer {case.answer} for {case.case_id}"
    return True, data, None


def process_snapshot(proc_root: Path = Path("/proc")) -> dict[int, int]:
    """Return exact llama-cli PID/RSS pairs without matching this Python source text."""
    found: dict[int, int] = {}
    try:
        processes = proc_root.iterdir()
        for entry in processes:
            if not entry.name.isdigit():
                continue
            try:
                if (entry / "comm").read_text(encoding="ascii").strip() != "llama-cli":
                    continue
                rss = 0
                for line in (entry / "status").read_text(encoding="ascii").splitlines():
                    if line.startswith("VmRSS:"):
                        rss = int(line.split()[1])
                        break
                found[int(entry.name)] = rss
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        pass
    return found


def _snapshot() -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = read_temperatures()
    values["memavailable_kib"] = read_memavailable_kib()
    return values


def active_temperature_limits(args: argparse.Namespace) -> dict[str, float]:
    """Return enforced thermal limits; explicit owner override keeps readings observational."""
    if getattr(args, "ignore_thermal_limits", False):
        return {}
    return {"cpu": args.cpu_stop_c, "gpu": args.gpu_stop_c, "htp": args.htp_stop_c,
            "battery": args.battery_stop_c, "socd": args.socd_stop_c}


def _render_report(args: argparse.Namespace, rows: list[dict[str, object]],
                   preflight: dict[str, float | int | None], limits: dict[str, float],
                   minimum_mem_kib: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine(), "prefix": os.environ.get("PREFIX")},
        "provider": "native-termux",
        "backend": args.backend,
        "prompt_suite_id": PROMPT_SUITE_ID,
        "scheduled_case_ids": [qualification_case_for_run(index).case_id
                                for index in range(1, args.runs + 1)],
        "max_tokens": args.max_tokens,
        "guards": {**limits, "minimum_memavailable_mib": minimum_mem_kib // 1024,
                   "note": "Conservative test guards selected for this run; not OEM-rated limits."},
        "thermal_limits_ignored": bool(getattr(args, "ignore_thermal_limits", False)),
        "preflight": preflight,
        "completed_runs": sum(row["status"] == "passed" for row in rows),
        "requested_runs": args.runs,
        "runs": rows,
    }


def _preflight_failure_report(args: argparse.Namespace, reason: str,
                              snapshot: dict[str, float | int | None],
                              limits: dict[str, float], minimum_mem_kib: int,
                              *, issues: list[str] | None = None,
                              pids: list[int] | None = None) -> dict[str, object]:
    report = _render_report(args, [], snapshot, limits, minimum_mem_kib)
    report.update({"ok": False, "error": reason, "snapshot": snapshot})
    if issues is not None:
        report["issues"] = issues
    if pids is not None:
        report["pids"] = pids
    return report


def collect_preflight(args: argparse.Namespace) -> dict[str, object]:
    """Capture one guarded resource sample without launching inference."""
    limits = active_temperature_limits(args)
    minimum_mem_kib = args.minimum_mem_mib * 1024
    required_sensor = {"cpu": "cpu", "vulkan": "gpu", "npu": "htp"}[args.backend]
    snapshot = _snapshot()
    if limits and ("cpu" not in snapshot or required_sensor not in snapshot):
        issues = [f"required {required_sensor}/CPU thermal zone is unavailable"]
    else:
        issues = resource_violations(snapshot, limits, minimum_mem_kib)
    pids = sorted(process_snapshot())
    if pids:
        issues.append("an existing llama-cli process is running; no inference was started")
    report = _render_report(args, [], snapshot, limits, minimum_mem_kib)
    report.update({"ok": not issues, "preflight_only": True,
                   "will_start_inference": False, "snapshot": snapshot,
                   "issues": issues, "pids": pids})
    if issues:
        report["error"] = "preflight checks failed; no inference started"
    return report


def _stop_process(proc: subprocess.Popen[str], sig: int, grace: float) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM if sig != signal.SIGTERM else signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


def run(args: argparse.Namespace) -> int:
    limits = active_temperature_limits(args)
    minimum_mem_kib = args.minimum_mem_mib * 1024
    preflight_report = collect_preflight(args)
    if not preflight_report["ok"]:
        print(json.dumps(preflight_report, ensure_ascii=False, indent=2), flush=True)
        return 2
    preflight = preflight_report["snapshot"]
    baseline_pids = process_snapshot()
    if baseline_pids:
        report = _preflight_failure_report(
            args, "an existing llama-cli process is running; refusing to interfere", preflight,
            limits, minimum_mem_kib, pids=sorted(baseline_pids))
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return 2

    rows: list[dict[str, object]] = []
    for index in range(1, args.runs + 1):
        case = qualification_case_for_run(index)
        before = _snapshot()
        issues = resource_violations(before, limits, minimum_mem_kib)
        if issues:
            rows.append({"run": index, "case_id": case.case_id, "status": "guard_blocked",
                         "issues": issues, "before": before})
            break
        command = [str(TX), "ai", "run", "--backend", args.backend,
                   "--max-tokens", str(args.max_tokens)]
        env = os.environ.copy()
        env.pop("LD_PRELOAD", None)
        started = time.monotonic()
        try:
            proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env, start_new_session=True)
        except OSError as exc:
            rows.append({"run": index, "status": "failed", "error": f"cannot start tx ({type(exc).__name__})"})
            break
        assert proc.stdin is not None
        try:
            proc.stdin.write(case.prompt + "\n")
            proc.stdin.close()
        except (BrokenPipeError, OSError) as exc:
            _stop_process(proc, signal.SIGINT, 8)
            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            rows.append({"run": index, "status": "failed",
                         "error": f"tx closed prompt input early ({type(exc).__name__})",
                         "exit_code": proc.returncode, "stdout_bytes": len(stdout.encode()),
                         "stderr_excerpt": stderr.strip()[:500]})
            break
        peak_rss_kib = 0
        peak_memavailable = before.get("memavailable_kib")
        samples: list[dict[str, float | int | None]] = []
        guard_issues: list[str] = []
        timeout_hit = False
        while proc.poll() is None:
            sample = _snapshot()
            samples.append(sample)
            guard_issues = resource_violations(sample, limits, minimum_mem_kib)
            available = sample.get("memavailable_kib")
            if available is not None and (peak_memavailable is None or int(available) < int(peak_memavailable)):
                peak_memavailable = available
            current_processes = process_snapshot()
            peak_rss_kib = max([peak_rss_kib, *current_processes.values()])
            if guard_issues:
                _stop_process(proc, signal.SIGINT, 8)
                break
            if time.monotonic() - started >= args.timeout:
                timeout_hit = True
                _stop_process(proc, signal.SIGINT, 8)
                break
            time.sleep(0.25)
        return_code = proc.wait()
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
        elapsed = round(time.monotonic() - started, 3)
        after = _snapshot()
        new_pids = sorted(set(process_snapshot()) - set(baseline_pids))
        if guard_issues:
            status, error, data = "guard_cancelled", "; ".join(guard_issues), None
        elif timeout_hit:
            status, error, data = "timed_out", f"run exceeded {args.timeout}s", None
        elif return_code != 0:
            status, error, data = "failed", f"tx exited {return_code}: {stderr.strip()[:500]}", None
        else:
            passed, data, error = parse_result(stdout, args.backend, case)
            status = "passed" if passed else "failed"
        if new_pids:
            status = "orphaned_inference"
            error = f"new llama-cli process(es) remain after tx exit: {new_pids}"
        row: dict[str, object] = {"run": index, "case_id": case.case_id, "status": status, "elapsed_seconds": elapsed,
            "exit_code": return_code, "peak_llama_cli_rss_kib": peak_rss_kib,
            "minimum_memavailable_kib": peak_memavailable, "thermal_samples": samples,
            "before": before, "after": after, "new_llama_cli_pids_remaining": new_pids}
        if data:
            # Fixed arithmetic prompts are safe to retain as auditable test evidence.
            row["result"] = dict(data)
            row["output_words"] = len(str(data.get("output", "")).split())
            row["answer_verified"] = status == "passed"
        if error:
            row["error"] = error
        rows.append(row)
        if status != "passed":
            break
        if index < args.runs and args.idle_seconds:
            idle_end = time.monotonic() + args.idle_seconds
            while time.monotonic() < idle_end:
                sample = _snapshot()
                issues = resource_violations(sample, limits, minimum_mem_kib)
                if issues:
                    rows.append({"run": index + 1,
                                 "case_id": qualification_case_for_run(index + 1).case_id,
                                 "status": "guard_blocked_after_idle",
                                 "issues": issues, "before": sample})
                    break
                time.sleep(min(0.5, idle_end - time.monotonic()))
            if rows[-1].get("status") == "guard_blocked_after_idle":
                break

    report = _render_report(args, rows, preflight, limits, minimum_mem_kib)
    report["ok"] = all(row.get("status") == "passed" for row in rows) and len(rows) == args.runs
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--backend", choices=sorted(BACKENDS), required=True)
    result.add_argument("--runs", type=int, default=3, help="bounded sequential calls (1..20)")
    result.add_argument("--max-tokens", type=int, default=8, help="per-call output limit (1..128)")
    result.add_argument("--timeout", type=int, default=90, help="per-call wall-clock limit in seconds")
    result.add_argument("--idle-seconds", type=float, default=5, help="guarded idle interval between calls")
    result.add_argument("--minimum-mem-mib", type=int, default=2048)
    result.add_argument("--cpu-stop-c", type=float, default=60)
    result.add_argument("--gpu-stop-c", type=float, default=60)
    result.add_argument("--htp-stop-c", type=float, default=60)
    result.add_argument("--battery-stop-c", type=float, default=45)
    result.add_argument("--socd-stop-c", type=float, default=70)
    result.add_argument("--ignore-thermal-limits", action="store_true",
                        help="continue despite temperature readings; memory, timeout, and process guards remain active")
    result.add_argument("--preview", action="store_true", help="print the test plan without reading device telemetry or running inference")
    result.add_argument("--preflight-only", action="store_true",
                        help="record one thermal/memory/process sample; never launch inference")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not 1 <= args.runs <= 20:
        parser().error("--runs must be between 1 and 20")
    if not 1 <= args.max_tokens <= 128:
        parser().error("--max-tokens must be between 1 and 128")
    if not 1 <= args.timeout <= 120:
        parser().error("--timeout must be between 1 and 120 seconds")
    if not 0 <= args.idle_seconds <= 300:
        parser().error("--idle-seconds must be between 0 and 300")
    if not 256 <= args.minimum_mem_mib <= 65536:
        parser().error("--minimum-mem-mib must be between 256 and 65536")
    if args.preview and args.preflight_only:
        parser().error("--preview and --preflight-only are separate modes")
    if args.preflight_only:
        report = collect_preflight(args)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return 0 if report["ok"] else 2
    if args.preview:
        print(json.dumps({"backend": args.backend, "prompt_suite_id": PROMPT_SUITE_ID,
                          "scheduled_case_ids": [qualification_case_for_run(index).case_id
                                                  for index in range(1, args.runs + 1)],
                          "runs": args.runs, "max_tokens": args.max_tokens,
                          "timeout_seconds": args.timeout, "idle_seconds": args.idle_seconds,
                          "test_guards_c": {"cpu": args.cpu_stop_c, "gpu": args.gpu_stop_c,
                              "htp": args.htp_stop_c, "battery": args.battery_stop_c,
                              "socd": args.socd_stop_c},
                          "minimum_mem_mib": args.minimum_mem_mib,
                          "thermal_limits_ignored": args.ignore_thermal_limits,
                          "guard_notice": "Temperature readings are advisory when --ignore-thermal-limits is set; memory and timeout bounds remain active.",
                          "will_start_inference": False}, indent=2))
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
