from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from lane import __version__
from lane.branches import parse_branch
from lane.cleanup import (
    CleanupError,
    close_pr,
    delete_remote_branch,
    ensure_clean_worktree,
    ensure_pr_merged,
)
from lane.forge import ForgeError, finalize_pr
from lane.init import run_init
from lane.openspec import OpenSpecError, create_spec, require_spec_archived
from lane.paseo import PaseoError, archive_worktree, create_worktree, list_worktrees
from lane.resolve import (
    resolve_current_directory,
    resolve_exact_branch,
    resolve_filesystem_path,
    resolve_pr_selector,
    resolve_slug,
)
from lane.review import ReviewError, run_review
from lane.state import STATE_SCHEMA, LaneState, read_state, state_to_dict, write_state
from lane.verify import VerifyError, run_verify


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
        "attach",
        "list",
    ]
    init = subparsers.add_parser("init", help="Initialize lane support.")
    init.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to initialize (default: current directory).",
    )
    init.set_defaults(handler=handle_init)

    cleanup = subparsers.add_parser("cleanup", help="Archive a completed lane.")
    cleanup.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    cleanup.add_argument(
        "--delete-remote-branch",
        action="store_true",
        help="Delete the remote branch after confirming the PR is merged.",
    )
    cleanup.set_defaults(handler=handle_cleanup)

    abort = subparsers.add_parser("abort", help="Archive a cancelled lane.")
    abort.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    abort.add_argument(
        "--discard",
        action="store_true",
        help="Allow aborting with uncommitted changes present.",
    )
    abort.add_argument(
        "--close-pr",
        action="store_true",
        help="Close the associated PR during abort.",
    )
    abort.add_argument(
        "--delete-remote-branch",
        action="store_true",
        help="Delete the remote branch during abort.",
    )
    abort.set_defaults(handler=handle_abort)

    finalize = subparsers.add_parser("finalize", help="Prepare a lane for PR handoff.")
    finalize.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    finalize.set_defaults(handler=handle_finalize)

    verify = subparsers.add_parser("verify", help="Run the lane verification command.")
    verify.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    verify.set_defaults(handler=handle_verify)

    review = subparsers.add_parser("review", help="Run lane review perspectives.")
    review.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    review.set_defaults(handler=handle_review)

    for name in pending_commands:
        command = subparsers.add_parser(name, help=f"{name} is not implemented yet.")
        command.set_defaults(handler=handle_not_implemented)

    return parser


def handle_start(args: argparse.Namespace) -> int:
    branch = parse_branch(args.branch)
    worktree = create_worktree(branch.branch, base=args.base, cwd=Path.cwd())
    state = LaneState(
        schema=STATE_SCHEMA,
        id=branch.slug,
        status="active",
        branch=branch.branch,
        base=args.base,
        path=worktree.path,
        spec=branch.slug,
        review="none",
        pr=None,
    )
    write_state(worktree.path, state)
    create_spec(
        branch.slug,
        schema=branch.spec_schema,
        description=f"Lane for {branch.branch}",
        cwd=worktree.path,
    )
    _print_state(state)
    return 0


def handle_init(args: argparse.Namespace) -> int:
    result = run_init(Path(args.path))
    print(f"ignored state: {result.gitignore}")
    print(f"lane-lite schema: {result.schema_dir}")
    if result.missing_tools:
        tools = ", ".join(result.missing_tools)
        print(f"warning: missing required tools on PATH: {tools}", file=sys.stderr)
    return 0


def handle_status(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    _print_state(state)
    return 0


def handle_cleanup(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    require_spec_archived(state.path, state.spec)
    ensure_pr_merged(state.pr, state.path)
    if args.delete_remote_branch:
        if state.pr is None:
            raise CleanupError("remote branch deletion requires a merged PR")
        delete_remote_branch(state.branch, state.path)
    result = archive_worktree(state.branch)
    print(f"archived: {result.name}")
    return 0


def handle_abort(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    ensure_clean_worktree(state.path, allow_dirty=args.discard)
    if args.close_pr:
        close_pr(state.pr, state.path)
    if args.delete_remote_branch:
        delete_remote_branch(state.branch, state.path)
    result = archive_worktree(state.branch)
    print(f"aborted: {result.name}")
    return 0


def handle_finalize(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    require_spec_archived(state.path, state.spec)
    verification = run_verify(state.path)
    if verification.exit_status != 0:
        print("verification failed; refusing to finalize", file=sys.stderr)
        return verification.exit_status
    result = finalize_pr(state, verification)
    write_state(state.path, replace(state, status="finalized", pr=result.pr_url))
    print(f"repo: {result.repo}")
    print(f"pr: {result.pr_url}")
    return 0


def handle_verify(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    result = run_verify(state.path)
    print(f"command: {result.command.label}")
    print(f"exit status: {result.exit_status}")
    print("summary:")
    print(result.summary)
    return result.exit_status


def handle_review(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    result = run_review(state.path)
    write_state(state.path, replace(state, review=result.review))
    print(f"review: {result.review}")
    if result.missing_agents:
        print(f"missing agents: {', '.join(result.missing_agents)}")
    for run in result.runs:
        print(f"{run.agent}: {run.exit_status}")
    return 0 if result.review in {"approve", "comment", "none"} else 1


def handle_not_implemented(args: argparse.Namespace) -> int:
    print(f"lane {args.command} is not implemented yet", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (
        CleanupError,
        ForgeError,
        OpenSpecError,
        PaseoError,
        ReviewError,
        ValueError,
        VerifyError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _print_state(state: LaneState) -> None:
    for key, value in state_to_dict(state).items():
        print(f"{key}: {value}")


def _resolve_lane(selector: str | None) -> LaneState:
    if selector is None:
        return resolve_current_directory(Path.cwd())

    candidate = Path(selector).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.exists():
        return resolve_filesystem_path(selector)

    lanes = _known_lane_states()
    if selector.startswith("#") or selector.startswith(("http://", "https://")):
        return resolve_pr_selector(selector, lanes)
    if "/" in selector:
        return resolve_exact_branch(selector, lanes)
    return resolve_slug(selector, lanes)


def _known_lane_states() -> list[LaneState]:
    lanes: list[LaneState] = []
    for worktree in list_worktrees():
        try:
            lanes.append(read_state(worktree.path))
        except FileNotFoundError:
            continue
    return lanes


if __name__ == "__main__":
    raise SystemExit(main())
