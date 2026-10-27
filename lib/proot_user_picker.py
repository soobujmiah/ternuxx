"""Interactive selection of an existing ordinary managed guest account."""
from __future__ import annotations

import argparse
import sys
from typing import TextIO


class UserPickerError(ValueError):
    pass


class UserPickerCancelled(UserPickerError):
    pass


def choose_user(users: list[str], *, selected: str | None = None,
                input_stream: TextIO | None = None,
                output_stream: TextIO | None = None) -> str:
    """Return an exact listed account; prompt only when selection is ambiguous."""
    if not users:
        raise UserPickerError("no ordinary guest account is available")
    if len(set(users)) != len(users):
        raise UserPickerError("guest account inventory contains duplicates")
    if selected is not None:
        if users.count(selected) != 1:
            raise UserPickerError("selected account is not an ordinary guest account")
        return selected
    if len(users) == 1:
        return users[0]
    if input_stream is None or output_stream is None:
        raise UserPickerError("multiple guest accounts require an attached terminal or --user NAME")
    print("Choose a guest account:", file=output_stream)
    for index, user in enumerate(users, 1):
        print(f"  {index}) {user}", file=output_stream)
    while True:
        print("Account number (q cancels): ", end="", file=output_stream, flush=True)
        answer = input_stream.readline()
        if not answer:
            raise UserPickerCancelled("account selection cancelled")
        answer = answer.strip()
        if answer.lower() == "q":
            raise UserPickerCancelled("account selection cancelled")
        if answer.isdecimal() and 1 <= int(answer) <= len(users):
            return users[int(answer) - 1]
        print(f"Choose a number from 1 to {len(users)}, or q to cancel.", file=output_stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--alias", default="debian")
    parser.add_argument("--user", help="select one exact ordinary guest account")
    args = parser.parse_args(argv)
    try:
        import proot_diagnostics
        users = proot_diagnostics.ordinary_guest_users(distro=args.alias, prefix=args.prefix)
        if args.user is not None or len(users) == 1:
            chosen = choose_user(users, selected=args.user)
        else:
            try:
                terminal = open("/dev/tty", "r+", encoding="utf-8")
            except OSError as exc:
                raise UserPickerError("multiple guest accounts require an attached terminal or --user NAME") from exc
            with terminal:
                chosen = choose_user(users, input_stream=terminal, output_stream=terminal)
    except (UserPickerError, OSError, ValueError) as exc:
        print(f"Account selection failed: {exc}", file=sys.stderr)
        return 2
    print(chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
