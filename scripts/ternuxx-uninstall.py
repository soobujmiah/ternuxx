#!/usr/bin/env python3
"""Preview/apply the full Ternuxx Native + PRoot uninstall."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import ternuxx_uninstall


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "apply"))
    parser.add_argument("--prefix", default=os.environ.get("PREFIX", "/data/data/com.termux/files/usr"))
    parser.add_argument("--home", default=os.environ.get("HOME", ""))
    parser.add_argument("--state-dir", default=os.environ.get("TERNUXX_STATE_DIR", ""))
    parser.add_argument("--plan-id")
    parser.add_argument("--confirmation")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    state_dir = args.state_dir or str(Path(args.home) / ".local/share/ternuxx")
    try:
        if args.action == "preview":
            if args.yes or args.plan_id or args.confirmation:
                raise ternuxx_uninstall.UninstallError("preview accepts no apply confirmation")
            result = ternuxx_uninstall.preview(prefix=args.prefix, home=args.home, state_dir=state_dir)
        else:
            if not args.yes or not args.plan_id or not args.confirmation:
                raise ternuxx_uninstall.UninstallError("apply requires --yes --plan-id and --confirmation UNINSTALL TERNUXX")
            result = ternuxx_uninstall.apply(prefix=args.prefix, home=args.home, state_dir=state_dir,
                plan_id=args.plan_id, confirmation=args.confirmation, confirmed=True)
        print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ternuxx_uninstall.UninstallError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}) if args.json else f"Uninstall stopped safely: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
