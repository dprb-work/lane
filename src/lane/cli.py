from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lane import __version__
from lane.branches import parse_branch
from lane.state import LaneState, find_state_path, read_state, state_to_dict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lane",
        description="Manage Paseo-native development lanes.",
    )
    parser.add_argument("--version", action="version", version=f"lane {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create a new Paseo-backed lane.")
    start.add_argument("branch", help="Branch in <type>/<slug> form.")
    start.add_argument(
        "--base", default="main", help="Base branch/ref (default: main)."
    )
    start.set_defaults(handler=handle_start)

    status = subparsers.add_parser("status", help="Show lane status.")
    status.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    status.set_defaults(handler=handle_status)

    pending_commands = [
        "init",
        "attach",
        "list",
        "verify",
        "review",
        "finalize",
        "cleanup",
        "abort",
    ]
    for name in pending_commands:
        command = subparsers.add_parser(name, help=f"{name} is not implemented yet.")
        command.set_defaults(handler=handle_not_implemented)

    return parser


def handle_start(args: argparse.Namespace) -> int:
    branch = parse_branch(args.branch)
    print(f"branch: {branch.branch}")
    print(f"id: {branch.slug}")
    print(f"spec schema: {branch.spec_schema}")
    print("paseo worktree creation is not implemented yet")
    return 2


def handle_status(args: argparse.Namespace) -> int:
    if args.selector is not None:
        print("explicit selectors are not implemented yet", file=sys.stderr)
        return 2

    path = find_state_path(Path.cwd())
    if path is None:
        print("no .lane/state.yaml found from current directory", file=sys.stderr)
        return 1

    state = read_state(path.parent.parent)
    _print_state(state)
    return 0


def handle_not_implemented(args: argparse.Namespace) -> int:
    print(f"lane {args.command} is not implemented yet", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _print_state(state: LaneState) -> None:
    for key, value in state_to_dict(state).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
