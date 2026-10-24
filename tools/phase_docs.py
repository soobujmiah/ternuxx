#!/usr/bin/env python3
"""Record a reviewed phase transition; generated phase dates use the UTC calendar."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "project" / "phase-state.json"
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
STATUS = ROOT / "docs" / "PHASE-STATUS.md"

README_START = "<!-- generated:phase-status:start -->"
README_END = "<!-- generated:phase-status:end -->"
ROADMAP_START = "<!-- generated:phase-table:start -->"
ROADMAP_END = "<!-- generated:phase-table:end -->"
ACTIVE_START = "<!-- generated:active-work:start -->"
ACTIVE_END = "<!-- generated:active-work:end -->"


def utc_date() -> str:
    """Return the UTC calendar date used by phase completed_on/skipped_on fields."""
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def load_state() -> dict:
    data = json.loads(STATE.read_text(encoding="utf-8"))
    phases = data.get("phases")
    if data.get("schema_version") != 1 or not isinstance(phases, list) or not phases:
        raise ValueError("Unsupported or empty phase-state schema")
    if any(not isinstance(p, dict) for p in phases):
        raise ValueError("Each phase entry must be an object")
    ids = [p.get("id") for p in phases]
    if len(ids) != len(set(ids)):
        raise ValueError("Phase IDs must be unique")
    allowed = {"planned", "in_progress", "completed", "skipped"}
    if any(p.get("status") not in allowed for p in phases):
        raise ValueError("Each phase must have a valid status")
    if any("optional" in p and not isinstance(p["optional"], bool) for p in phases):
        raise ValueError("Optional phase metadata must be boolean")
    active = data.get("active_phase")
    active_rows = [p for p in phases if p["status"] == "in_progress"]
    if active is None:
        if active_rows or any(p["status"] == "planned" for p in phases):
            raise ValueError("active_phase is missing while phases remain")
    elif len(active_rows) != 1 or active_rows[0]["id"] != active:
        raise ValueError("active_phase must identify the sole in-progress phase")
    validate_phase_order(phases, active)
    return data


def validate_phase_order(phases: list[dict], active: str | None) -> None:
    if any(p["status"] == "skipped" and p.get("optional") is not True for p in phases):
        raise ValueError("Only explicitly optional phases may be skipped")
    if active is None:
        if any(p["status"] == "planned" for p in phases):
            raise ValueError("active_phase is missing while phases remain")
        return
    active_index = next(i for i, phase in enumerate(phases) if phase["id"] == active)
    if any(p["status"] not in {"completed", "skipped"} for p in phases[:active_index]):
        raise ValueError("Every earlier phase must be completed or explicitly skipped")
    if any(p["status"] != "planned" for p in phases[active_index + 1:]):
        raise ValueError("Every later phase must remain planned until its turn")


def replace_block(document: str, start: str, end: str, body: str, label: str) -> str:
    if document.count(start) != 1 or document.count(end) != 1:
        raise ValueError(f"{label} must contain exactly one generated block")
    before, remainder = document.split(start, 1)
    _, after = remainder.split(end, 1)
    return f"{before}{start}\n{body.rstrip()}\n{end}{after}"


def render(state: dict) -> dict[Path, str]:
    phases = state["phases"]
    complete = sum(p["status"] == "completed" for p in phases)
    skipped = sum(p["status"] == "skipped" for p in phases)
    resolved = complete + skipped
    active = next((p for p in phases if p["status"] == "in_progress"), None)
    progress = f"{resolved}/{len(phases)} phases resolved ({complete} completed, {skipped} skipped)"
    if active:
        current = f"**Current phase:** {active['id']} — {active['title']}"
    else:
        current = ("**Current phase:** All required roadmap phases are resolved." if skipped
                   else "**Current phase:** All roadmap phases are complete.")

    # Keep the README status compact. Detailed summaries and the active next
    # action belong to ROADMAP/PHASE-STATUS and should not be copied into a
    # third generated location.
    readme_body = (f"{current}\n\n**Progress:** {progress}\n\n"
                   "[Roadmap and active work](docs/ROADMAP.md) · "
                   "[Phase status and evidence](docs/PHASE-STATUS.md)")
    readme = replace_block(README.read_text(encoding="utf-8"), README_START, README_END, readme_body, "README")

    table_rows = ["| ID | Phase | Status | Completed / skipped |", "|---|---|---|---|"]
    for phase in phases:
        table_rows.append(
            f"| {phase['id']} | {phase['title']} | {phase['status']} | {phase.get('completed_on') or ('skipped ' + phase['skipped_on'] if phase.get('skipped_on') else '—')} |"
        )
    roadmap = replace_block(
        ROADMAP.read_text(encoding="utf-8"),
        ROADMAP_START,
        ROADMAP_END,
        "\n".join(table_rows),
        "ROADMAP",
    )
    if active:
        active_work = (
            f"**Active phase:** {active['id']} — {active['title']}\n\n"
            f"**Next action:** {active.get('next_action') or 'Choose the next evidence-backed item from this phase.'}\n\n"
            "Complete this item and update its evidence before moving to the next item or phase."
        )
    else:
        active_work = ("All required phases are resolved; see evidence for completed gates and skipped optional phases."
                       if skipped else "All phases are complete; see their evidence records for accepted gates.")
    roadmap = replace_block(roadmap, ACTIVE_START, ACTIVE_END, active_work, "ROADMAP active work")

    status_lines = [
        "# Phase status",
        "",
        "> Generated by `python3 tools/phase_docs.py`. Edit `project/phase-state.json` only through the phase workflow; do not edit this report by hand.",
        "",
        f"**Progress:** {progress}",
        f"**Active phase:** {active['id']} — {active['title']}" if active else "**Active phase:** none",
        "",
    ]
    for phase in phases:
        status_lines += [f"## {phase['id']} — {phase['title']}", "", f"**Status:** {phase['status']}"]
        if phase.get("completed_on"):
            status_lines.append(f"**Completed:** {phase['completed_on']}")
        if phase.get("summary"):
            status_lines += ["", phase["summary"]]
        if phase.get("next_action") and phase["status"] == "in_progress":
            status_lines += ["", f"**Next action:** {phase['next_action']}"]
        if phase.get("evidence"):
            status_lines += ["", "Evidence:"]
            for item in phase["evidence"]:
                rel = os.path.relpath(ROOT / item, STATUS.parent)
                status_lines.append(f"- [{item}]({rel})")
        status_lines.append("")
    return {README: readme, ROADMAP: roadmap, STATUS: "\n".join(status_lines).rstrip() + "\n"}


def write_all(outputs: dict[Path, str], state: dict | None = None) -> None:
    payloads = dict(outputs)
    if state is not None:
        payloads[STATE] = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    staged: list[tuple[Path, Path]] = []
    try:
        for target, content in payloads.items():
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temp = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            staged.append((temp, target))
        for temp, target in staged:
            os.replace(temp, target)
    finally:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)


def validate_evidence_content(content: str, phase_id: str, *, completion: bool = True,
                              skip: bool = False) -> None:
    required = [f"Phase: {chr(96)}{phase_id}{chr(96)}", "## Evidence"]
    if skip:
        required += ["Gate: SKIP", "## Acceptance criteria"]
    elif completion:
        required += ["Gate: PASS", "## Acceptance criteria"]
    if any(marker not in content for marker in required):
        detail = ("Gate: SKIP, '## Acceptance criteria', and " if skip else
                  "Gate: PASS, '## Acceptance criteria', and " if completion else "")
        raise ValueError(f"Evidence must identify {phase_id} and include {detail}'## Evidence'")


def evidence_path(value: str, phase_id: str, *, completion: bool = True,
                 skip: bool = False) -> tuple[str, Path]:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Evidence paths must stay inside the repository")
    resolved = (ROOT / candidate).resolve(strict=True)
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        raise ValueError("Evidence must be a file inside the repository")
    validate_evidence_content(resolved.read_text(encoding="utf-8"), phase_id,
                              completion=completion, skip=skip)
    return candidate.as_posix(), resolved



def start_planned_phase(state: dict, phase_id: str) -> None:
    if state.get("active_phase") is not None:
        raise ValueError(f"Cannot start a phase while {state['active_phase']} is active")
    phase = next(p for p in state["phases"] if p["id"] == phase_id)
    if phase.get("status") != "planned":
        raise ValueError("Only a planned phase can be started")
    index = state["phases"].index(phase)
    if any(p["status"] not in {"completed", "skipped"} for p in state["phases"][:index]):
        raise ValueError("Every earlier phase must be resolved before this phase starts")
    phase["status"] = "in_progress"
    state["active_phase"] = phase["id"]


def skip_optional_phase(state: dict, phase_id: str, summary: str, evidence: list[str],
                        *, skipped_on: str | None = None) -> None:
    phase = next(p for p in state["phases"] if p["id"] == phase_id)
    if phase.get("status") != "in_progress" or phase.get("optional") is not True:
        raise ValueError("Only the active phase explicitly marked optional can be skipped")
    phase.update(status="skipped",
                 skipped_on=skipped_on or utc_date(),
                 summary=summary, evidence=evidence)
    index = state["phases"].index(phase)
    next_phase = next((p for p in state["phases"][index + 1:] if p["status"] == "planned"), None)
    if next_phase:
        next_phase["status"] = "in_progress"
        state["active_phase"] = next_phase["id"]
    else:
        state["active_phase"] = None

def revise_resolved_phase(state: dict, phase_id: str, *, title: str | None = None,
                          summary: str | None = None, clear_next_action: bool = False,
                          reason: str) -> None:
    """Correct stale descriptive metadata on a closed phase without reopening its gate."""
    phase = next(p for p in state["phases"] if p["id"] == phase_id)
    if phase.get("status") not in {"completed", "skipped"}:
        raise ValueError("Only a completed or skipped phase can have its metadata revised")
    reason = reason.strip()
    if not reason or "\n" in reason or "\r" in reason:
        raise ValueError("Revision reason must be a non-empty single line")
    if title is not None:
        title = title.strip()
        if not title or "\n" in title or "\r" in title:
            raise ValueError("Phase title must be a non-empty single line")
        phase["title"] = title
    if summary is not None:
        summary = summary.strip()
        if not summary or "\n" in summary or "\r" in summary:
            raise ValueError("Phase summary must be a non-empty single line")
        phase["summary"] = summary
    if clear_next_action:
        phase.pop("next_action", None)
    phase.setdefault("revision_notes", []).append({"date": utc_date(), "reason": reason})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("refresh", help="regenerate phase status docs from the recorded state")
    update = sub.add_parser("update", help="record verified progress while keeping the active phase in progress")
    update.add_argument("phase_id")
    update.add_argument("--evidence", action="append", required=True, help="repo-relative evidence file; repeatable")
    update.add_argument("--summary", required=True, help="updated one-line phase summary")
    update.add_argument("--next-action", help="updated next action for the active phase")
    annotate = sub.add_parser("annotate", help="record preparatory evidence for a planned phase without activating or completing it")
    annotate.add_argument("phase_id")
    annotate.add_argument("--evidence", action="append", required=True, help="repo-relative evidence file; repeatable")
    annotate.add_argument("--summary", required=True, help="one-line preparatory progress summary")
    annotate.add_argument("--next-action", help="next action to take when this phase becomes active")
    annotate.add_argument("--optional", action="store_true", help="mark this planned phase as explicitly skippable")
    start = sub.add_parser("start", help="activate the next planned phase after all earlier gates are resolved")
    start.add_argument("phase_id")
    plan = sub.add_parser("plan", help="append a required roadmap phase and optionally activate it")
    plan.add_argument("phase_id")
    plan.add_argument("title")
    plan.add_argument("--summary", required=True, help="initial evidence-backed phase status")
    plan.add_argument("--next-action", required=True, help="first concrete phase action")
    plan.add_argument("--start", action="store_true", help="activate this new phase now")
    skip = sub.add_parser("skip", help="skip the active optional phase with reviewed evidence")
    skip.add_argument("phase_id")
    skip.add_argument("--evidence", action="append", required=True, help="repo-relative evidence file; repeatable")
    skip.add_argument("--summary", required=True, help="short evidence-backed reason the optional phase is not selected")
    complete = sub.add_parser("complete", help="record a reviewed completion for the active phase")
    complete.add_argument("phase_id")
    complete.add_argument("--evidence", action="append", required=True, help="repo-relative evidence file; repeatable")
    complete.add_argument("--summary", required=True, help="short gate result summary")
    revise = sub.add_parser("revise", help="correct descriptive metadata on a closed phase without reopening its gate")
    revise.add_argument("phase_id")
    revise.add_argument("--reason", required=True, help="why the descriptive metadata needs correction")
    revise.add_argument("--title", help="correct the phase title")
    revise.add_argument("--summary", help="correct the phase summary")
    revise.add_argument("--clear-next-action", action="store_true", help="remove a stale next action from a closed phase")
    args = parser.parse_args()

    try:
        state = load_state()
        if args.command == "refresh":
            write_all(render(state))
            print("Generated README, roadmap status, and docs/PHASE-STATUS.md from recorded state.")
            return 0
        if args.command == "revise":
            if not args.title and not args.summary and not args.clear_next_action:
                raise ValueError("Provide a title, summary, or --clear-next-action revision")
            revise_resolved_phase(state, args.phase_id, title=args.title, summary=args.summary,
                                  clear_next_action=args.clear_next_action, reason=args.reason)
            write_all(render(state), state)
            print(f"Revised descriptive metadata for closed {args.phase_id} without changing its gate.")
            return 0
        if args.command == "start":
            start_planned_phase(state, args.phase_id)
            write_all(render(state), state)
            print(f"Activated {args.phase_id} and refreshed generated phase documentation.")
            return 0

        if args.command == "plan":
            if any(p["id"] == args.phase_id for p in state["phases"]):
                raise ValueError("Phase ID already exists")
            if any(p["status"] == "planned" for p in state["phases"]):
                raise ValueError("Resolve existing planned phases before appending another")
            phase = {"id": args.phase_id, "title": args.title, "status": "planned",
                     "summary": args.summary, "evidence": [], "next_action": args.next_action}
            state["phases"].append(phase)
            if args.start:
                start_planned_phase(state, args.phase_id)
            write_all(render(state), state)
            print(f"Added {args.phase_id} to the roadmap" + (" and activated it." if args.start else "."))
            return 0

        summary = args.summary.strip()
        summary_limit = 10000 if args.command in {"update", "annotate"} else 500
        if not summary or len(summary) > summary_limit or "\n" in summary or "\r" in summary:
            raise ValueError(f"Summary must be one line with 1–{summary_limit} characters")
        if args.command != "annotate" and state.get("active_phase") != args.phase_id:
            raise ValueError(f"Only the active phase can be updated (active: {state.get('active_phase') or 'none'})")
        phase = next(p for p in state["phases"] if p["id"] == args.phase_id)
        evidence = [evidence_path(item, args.phase_id, completion=args.command == "complete",
                                  skip=args.command == "skip")[0] for item in args.evidence]
        if args.command == "annotate":
            if phase["status"] != "planned":
                raise ValueError("Preparatory annotations require a planned phase")
            merged = list(dict.fromkeys([*phase.get("evidence", []), *evidence]))
            phase.update(summary=summary, evidence=merged)
            if args.optional:
                phase["optional"] = True
            if args.next_action:
                action = args.next_action.strip()
                if not action or "\n" in action or "\r" in action:
                    raise ValueError("Next action must be a non-empty single line")
                phase["next_action"] = action
            write_all(render(state), state)
            print(f"Recorded preparatory {args.phase_id} evidence without changing phase status.")
            return 0
        if args.command == "skip":
            skip_optional_phase(state, args.phase_id, summary, evidence)
            write_all(render(state), state)
            print(f"Skipped optional {args.phase_id} with reviewed evidence and advanced the active phase.")
            return 0
        if args.command == "update":
            if phase["status"] != "in_progress":
                raise ValueError("Only an in-progress phase can record incremental evidence")
            merged = list(dict.fromkeys([*phase.get("evidence", []), *evidence]))
            phase.update(summary=summary, evidence=merged)
            if args.next_action:
                action = args.next_action.strip()
                if not action or "\n" in action or "\r" in action:
                    raise ValueError("Next action must be a non-empty single line")
                phase["next_action"] = action
            write_all(render(state), state)
            print(f"Recorded {args.phase_id} progress and refreshed generated phase documentation.")
            return 0
        phase.update(
            status="completed",
            completed_on=utc_date(),
            summary=summary,
            evidence=evidence,
        )
        index = state["phases"].index(phase)
        next_phase = next((p for p in state["phases"][index + 1:] if p["status"] == "planned"), None)
        if next_phase:
            next_phase["status"] = "in_progress"
            state["active_phase"] = next_phase["id"]
        else:
            state["active_phase"] = None
        write_all(render(state), state)
        print(f"Recorded {args.phase_id} completion and refreshed generated phase documentation.")
        return 0
    except (OSError, ValueError, KeyError, StopIteration, json.JSONDecodeError) as error:
        print(f"phase_docs: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
