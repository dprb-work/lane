from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from lane import __version__
from lane.branches import parse_branch
from lane.cleanup import (
    CleanupError,
    cleanup_archive_root,
    close_pr,
    delete_remote_branch,
    ensure_clean_worktree,
    ensure_pr_merged,
    write_cleanup_archive_summary,
)
from lane.doctor import Diagnostic, has_failures, run_doctor
from lane.forge import (
    ForgeError,
    create_draft_pr,
    finalize_pr,
    mark_pr_ready,
    push_branch,
    update_pr_metadata,
)
from lane.init import (
    InitError,
    compact_opencode_registration_note,
    compact_tool_requirement_note,
    run_init,
)
from lane.lane_target import LaneTarget, LaneTargetError, resolve_lane_target
from lane.openspec import (
    OpenSpecError,
    active_spec_path,
    create_spec,
    require_spec_archived,
)
from lane.paseo import (
    PaseoError,
    archive_worktree,
    checkout_branch_worktree,
    create_worktree,
    list_worktrees,
    rename_current_branch,
)
from lane.resolve import (
    resolve_current_directory,
    resolve_filesystem_path,
)
from lane.review import ReviewError, run_review
from lane.run import RunError, run_lane_command
from lane.state import (
    STATE_SCHEMA,
    LaneState,
    find_state_path,
    read_state,
    state_to_dict,
    write_state,
)
from lane.status import collect_status_health
from lane.sync import SyncResult, sync_lane_state
from lane.verify import (
    VerifyError,
    VerifyResult,
    current_head,
    require_fresh_verification,
    run_verify,
    verification_state,
    verify_result_from_state,
)


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
    status.add_argument(
        "--json",
        action="store_true",
        help="Print stored state and health facts as JSON.",
    )
    status.set_defaults(handler=handle_status)

    list_command = subparsers.add_parser("list", help="List known lanes.")
    list_command.add_argument(
        "--json",
        action="store_true",
        help="Print known lanes as JSON.",
    )
    list_command.set_defaults(handler=handle_list)

    attach = subparsers.add_parser(
        "attach",
        help="Attach an existing Paseo workspace to lane state.",
    )
    attach.add_argument(
        "selector",
        nargs="?",
        help="Paseo workspace selector; omitted means current directory.",
    )
    attach.set_defaults(handler=handle_attach)

    init = subparsers.add_parser("init", help="Initialize lane support.")
    init.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to initialize (default: current directory).",
    )
    init.set_defaults(handler=handle_init)

    doctor = subparsers.add_parser("doctor", help="Run read-only diagnostics.")
    doctor.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository or lane path to inspect (default: current directory).",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print diagnostics as JSON.",
    )
    doctor.set_defaults(handler=handle_doctor)

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
    finalize.add_argument(
        "--no-verify",
        action="store_true",
        help="Reuse an already fresh verification result instead of rerunning.",
    )
    finalize.add_argument(
        "--force-with-lease",
        action="store_true",
        help="Push rewritten history with git push --force-with-lease.",
    )
    finalize.add_argument(
        "--json",
        action="store_true",
        help="Print finalize result as JSON.",
    )
    finalize.set_defaults(handler=handle_finalize)

    push = subparsers.add_parser("push", help="Publish a verified lane branch.")
    push.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    push.add_argument(
        "--no-verify",
        action="store_true",
        help="Reuse an already fresh verification result instead of rerunning.",
    )
    push.add_argument(
        "--force-with-lease",
        action="store_true",
        help="Push rewritten history with git push --force-with-lease.",
    )
    push.add_argument(
        "--json",
        action="store_true",
        help="Print push result as JSON.",
    )
    push.set_defaults(handler=handle_push)

    sync = subparsers.add_parser("sync", help="Refresh stored lane state.")
    sync.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    sync.add_argument(
        "--json",
        action="store_true",
        help="Print refreshed state and changes as JSON.",
    )
    sync.set_defaults(handler=handle_sync)

    verify = subparsers.add_parser("verify", help="Run the lane verification command.")
    verify.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    verify.add_argument(
        "--json",
        action="store_true",
        help="Print verification result as JSON.",
    )
    verify.set_defaults(handler=handle_verify)

    run = subparsers.add_parser("run", help="Run a command in a lane workspace.")
    run.add_argument(
        "run_args",
        nargs=argparse.REMAINDER,
        help="Optional lane selector followed by -- and command argv.",
    )
    run.set_defaults(handler=handle_run)

    review = subparsers.add_parser("review", help="Run lane review perspectives.")
    review.add_argument(
        "selector",
        nargs="?",
        help="Lane selector; omitted means current directory.",
    )
    review.add_argument(
        "--review-agent",
        action="append",
        dest="review_agents",
        help="Paseo provider mode/review agent name to run; repeat for multiple.",
    )
    review.add_argument(
        "--review-judge",
        help="Paseo provider mode/review agent name for the final judge phase.",
    )
    review.add_argument(
        "--json",
        action="store_true",
        help="Print review result as JSON.",
    )
    review.set_defaults(handler=handle_review)

    return parser


def handle_start(args: argparse.Namespace) -> int:
    branch = parse_branch(args.branch)
    worktree = create_worktree(
        branch.branch,
        base=args.base,
        cwd=Path.cwd(),
        worktree_slug=branch.slug,
    )
    if worktree.branch != branch.branch:
        try:
            rename_current_branch(branch.branch, cwd=worktree.path)
        except PaseoError as error:
            try:
                archive_worktree(worktree.name)
            except PaseoError as archive_error:
                raise PaseoError(
                    "branch rename failed and rollback archive failed: "
                    f"{error}; {archive_error}"
                ) from error
            raise
        worktree = replace(worktree, branch=branch.branch)
    state = _new_lane_state(
        branch=branch.branch,
        lane_id=branch.slug,
        base=args.base,
        path=worktree.path,
        pr=None,
    )
    try:
        create_spec(
            branch.slug,
            schema=branch.spec_schema,
            description=f"Lane for {branch.branch}",
            cwd=worktree.path,
        )
    except OpenSpecError as error:
        try:
            archive_worktree(worktree.name)
        except PaseoError as archive_error:
            raise OpenSpecError(
                "spec creation failed and rollback archive failed: "
                f"{error}; {archive_error}"
            ) from error
        raise
    write_state(worktree.path, state)
    try:
        repo = push_branch(state)
        result = create_draft_pr(state)
    except ForgeError as error:
        print(f"warning: draft PR not created: {error}", file=sys.stderr)
    else:
        state = replace(state, pr=result.pr_url)
        write_state(worktree.path, state)
        print(f"repo: {repo}")
        print(f"draft pr: {result.pr_url}")
    _print_state(state)
    return 0


def handle_init(args: argparse.Namespace) -> int:
    result = run_init(Path(args.path))
    print(f"ignored state: {result.gitignore}")
    print(f"agent instructions {result.agents_action}: {result.agents}")
    print(f"paseo config {result.paseo_config_action}: {result.paseo_config}")
    print(f"lane-lite schema: {result.schema_dir}")
    print(compact_opencode_registration_note())
    print(compact_tool_requirement_note())
    if result.paseo_version is not None:
        print(f"paseo CLI: {result.paseo_version}")
    if result.paseo_current_version is not None:
        print(f"paseo current: {result.paseo_current_version}")
    if result.paseo_upgrade_hint is not None:
        print(f"warning: {result.paseo_upgrade_hint}", file=sys.stderr)
    if result.missing_tools:
        tools = ", ".join(result.missing_tools)
        print(f"warning: missing required tools on PATH: {tools}", file=sys.stderr)
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    diagnostics = run_doctor(Path(args.path))
    if args.json:
        _print_json(
            {
                "diagnostics": [asdict(diagnostic) for diagnostic in diagnostics],
                "has_failures": has_failures(diagnostics),
            }
        )
        return 1 if has_failures(diagnostics) else 0
    _print_diagnostics(diagnostics)
    return 1 if has_failures(diagnostics) else 0


def handle_status(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    if args.json:
        _print_status_json(state)
        return 0
    _print_state(state)
    _print_status_health(state)
    return 0


def handle_list(args: argparse.Namespace) -> int:
    lanes = sorted(_known_lane_states(), key=lambda lane: (lane.id, lane.branch))
    if args.json:
        _print_json({"lanes": [state_to_dict(state) for state in lanes]})
        return 0
    _print_lane_table(lanes)
    return 0


def handle_attach(args: argparse.Namespace) -> int:
    state = _attach_lane(args.selector)
    _print_state(state)
    return 0


def handle_cleanup(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    require_spec_archived(state.path, state.spec)
    ensure_pr_merged(state.pr, state.path)
    archive_root = cleanup_archive_root(Path.cwd(), state.path)
    summary_path = write_cleanup_archive_summary(
        archive_root,
        state,
        merge_status="merged",
        archive_status="pending",
    )
    if args.delete_remote_branch:
        if state.pr is None:
            raise CleanupError("remote branch deletion requires a merged PR")
        delete_remote_branch(state.branch, state.path)
    result = archive_worktree(state.id)
    summary_path = write_cleanup_archive_summary(
        archive_root,
        state,
        merge_status="merged",
        archive_status="archived",
        removed_agents=result.removed_agents,
    )
    print(f"archived: {result.name}")
    print(f"archive summary: {summary_path}")
    return 0


def handle_abort(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    ensure_clean_worktree(state.path, allow_dirty=args.discard)
    if args.close_pr:
        close_pr(state.pr, state.path)
    if args.delete_remote_branch:
        delete_remote_branch(state.branch, state.path)
    result = archive_worktree(state.id)
    print(f"aborted: {result.name}")
    return 0


def handle_finalize(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    require_spec_archived(state.path, state.spec)
    if state.review != "approve":
        raise ForgeError("finalize requires approved agent review; run `lane review`")
    state, verification = _publication_verification(state, no_verify=args.no_verify)
    if verification.exit_status != 0:
        if args.json:
            _print_json(
                {
                    "error": "verification failed; refusing to finalize",
                    "state": state_to_dict(state),
                    "verification": _verification_result_to_dict(verification),
                }
            )
            return verification.exit_status
        print("verification failed; refusing to finalize", file=sys.stderr)
        _print_verification_result(verification)
        return verification.exit_status
    push_branch(state, force_with_lease=args.force_with_lease)
    result = finalize_pr(state, verification)
    mark_pr_ready(result.pr_url, state.path)
    state = replace(state, status="finalized", pr=result.pr_url)
    write_state(state.path, state)
    if args.json:
        _print_json(
            {
                "repo": result.repo,
                "pr": result.pr_url,
                "state": state_to_dict(state),
                "verification": _verification_result_to_dict(verification),
            }
        )
        return 0
    print(f"repo: {result.repo}")
    print(f"pr: {result.pr_url}")
    return 0


def handle_push(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    state, verification = _publication_verification(state, no_verify=args.no_verify)
    if verification.exit_status != 0:
        if args.json:
            _print_json(
                {
                    "error": "verification failed; refusing to push",
                    "state": state_to_dict(state),
                    "verification": _verification_result_to_dict(verification),
                }
            )
            return verification.exit_status
        print("verification failed; refusing to push", file=sys.stderr)
        _print_verification_result(verification)
        return verification.exit_status
    repo = push_branch(state, force_with_lease=args.force_with_lease)
    update_pr_metadata(state, verification)
    if args.json:
        _print_json(
            {
                "repo": repo,
                "pushed": state.branch,
                "state": state_to_dict(state),
                "verification": _verification_result_to_dict(verification),
            }
        )
        return 0
    print(f"repo: {repo}")
    print(f"pushed: {state.branch}")
    return 0


def handle_sync(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    result = sync_lane_state(state)
    write_state(result.state.path, result.state)
    if args.json:
        _print_json(_sync_result_to_dict(result))
        return 0
    _print_state(result.state)
    _print_sync_result(result)
    return 0


def handle_verify(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    result = run_verify(state.path)
    if result.exit_status == 0:
        head = current_head(state.path)
        state = replace(state, verification=verification_state(result, head))
        write_state(state.path, state)
    if args.json:
        _print_json(
            {
                "state": state_to_dict(state),
                "verification": _verification_result_to_dict(result),
            }
        )
        return result.exit_status
    _print_verification_result(result)
    return result.exit_status


def handle_run(args: argparse.Namespace) -> int:
    selector, argv = _parse_run_args(args.run_args)
    state = _resolve_lane(selector)
    result = run_lane_command(state.path, argv, capture_output=False)
    return result.exit_status


def _parse_run_args(args: list[str]) -> tuple[str | None, list[str]]:
    if not args:
        raise RunError("missing command after `--`")
    if args[0] == "--":
        argv = args[1:]
        if not argv:
            raise RunError("missing command after `--`")
        return None, argv
    try:
        separator = args.index("--")
    except ValueError as error:
        raise RunError("missing `--` before command") from error
    if separator != 1:
        raise RunError("lane run accepts at most one selector before `--`")
    argv = args[separator + 1 :]
    if not argv:
        raise RunError("missing command after `--`")
    return args[0], argv


def _publication_verification(
    state: LaneState,
    *,
    no_verify: bool,
) -> tuple[LaneState, VerifyResult]:
    if no_verify:
        head = current_head(state.path)
        fresh = require_fresh_verification(state.verification, head)
        return state, verify_result_from_state(fresh)

    result = run_verify(state.path)
    if result.exit_status != 0:
        return state, result
    head = current_head(state.path)
    state = replace(state, verification=verification_state(result, head))
    write_state(state.path, state)
    return state, result


def handle_review(args: argparse.Namespace) -> int:
    state = _resolve_lane(args.selector)
    agents = tuple(args.review_agents) if args.review_agents else None
    kwargs = {}
    if args.review_judge:
        kwargs["judge"] = args.review_judge
    result = (
        run_review(state.path, expected=agents, **kwargs)
        if agents is not None
        else run_review(state.path, **kwargs)
    )
    state = replace(state, review=result.review)
    write_state(state.path, state)
    if args.json:
        _print_json(
            {
                "review": result.review,
                "state": state_to_dict(state),
                "missing_agents": list(result.missing_agents),
                "runs": [asdict(run) for run in result.runs],
            }
        )
        return 0 if result.review in {"approve", "comment", "none"} else 1
    print(f"review: {result.review}")
    if result.missing_agents:
        print(f"missing agents: {', '.join(result.missing_agents)}")
    for run in result.runs:
        suffix = "" if run.paseo_agent_id is None else f" ({run.paseo_agent_id})"
        print(f"{run.agent}: {run.exit_status}{suffix}")
    return 0 if result.review in {"approve", "comment", "none"} else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (
        CleanupError,
        ForgeError,
        InitError,
        LaneTargetError,
        OpenSpecError,
        PaseoError,
        ReviewError,
        RunError,
        ValueError,
        VerifyError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _print_state(state: LaneState) -> None:
    for key, value in state_to_dict(state).items():
        print(f"{key}: {value}")


def _print_status_health(state: LaneState) -> None:
    health = collect_status_health(state)
    print(f"health.worktree: {health.worktree}")
    print(f"health.head: {health.head}")
    print(f"health.upstream: {health.upstream}")
    print(f"health.verification: {health.verification}")
    print(f"health.spec: {health.spec}")
    print(f"health.pr: {health.pr}")


def _print_status_json(state: LaneState) -> None:
    health = collect_status_health(state)
    _print_json(
        {
            "state": state_to_dict(state),
            "health": asdict(health),
        }
    )


def _verification_result_to_dict(result: VerifyResult) -> dict[str, object]:
    return {
        "command": {
            "argv": result.command.argv,
            "label": result.command.label,
        },
        "exit_status": result.exit_status,
        "summary": result.summary,
    }


def _sync_result_to_dict(result: SyncResult) -> dict[str, object]:
    return {
        "state": state_to_dict(result.state),
        "changes": list(result.changes),
        "warnings": list(result.warnings),
    }


def _print_json(raw: object) -> None:
    print(json.dumps(raw, indent=2))


def _print_verification_result(result: VerifyResult) -> None:
    print(f"command: {result.command.label}")
    print(f"exit status: {result.exit_status}")
    print("summary:")
    print(result.summary)


def _print_sync_result(result: SyncResult) -> None:
    print("changes:")
    if result.changes:
        for change in result.changes:
            print(f"- {change}")
    else:
        print("- none")
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


def _print_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        print(f"{diagnostic.status}: {diagnostic.name}: {diagnostic.detail}")


def _print_lane_table(lanes: list[LaneState]) -> None:
    headers = ("ID", "STATUS", "BRANCH", "REVIEW", "PR", "PATH")
    rows = [
        (
            state.id,
            state.status,
            state.branch,
            state.review,
            state.pr or "-",
            str(state.path),
        )
        for state in lanes
    ]
    widths = [
        max(len(row[index]) for row in (headers, *rows))
        for index in range(len(headers))
    ]
    print(_format_lane_row(headers, widths))
    for row in rows:
        print(_format_lane_row(row, widths))


def _format_lane_row(row: tuple[str, ...], widths: list[int]) -> str:
    padded = [value.ljust(widths[index]) for index, value in enumerate(row[:-1])]
    return "  ".join([*padded, row[-1]])


def _resolve_lane(selector: str | None) -> LaneState:
    if selector is None:
        return resolve_current_directory(Path.cwd())

    candidate = Path(selector).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.exists():
        return resolve_filesystem_path(selector)

    lanes = _known_lane_states()
    target = resolve_lane_target(selector, lanes, cwd=Path.cwd())
    if target.state is not None:
        return target.state
    return _materialize_lane_target(target)


def _materialize_lane_target(target: LaneTarget) -> LaneState:
    branch = parse_branch(target.branch)
    worktree = checkout_branch_worktree(branch.branch, cwd=Path.cwd())
    state = _new_lane_state(
        branch=branch.branch,
        lane_id=worktree.name,
        base=target.base,
        path=worktree.path,
        pr=target.pr_url,
        spec=branch.slug,
    )
    write_state(worktree.path, state)
    return state


def _attach_lane(selector: str | None) -> LaneState:
    worktree, target = _resolve_attach_worktree(selector)
    existing_state_path = find_state_path(worktree.path)
    if existing_state_path is not None:
        return read_state(existing_state_path.parent.parent)

    branch = parse_branch(worktree.branch)
    state = _new_lane_state(
        branch=branch.branch,
        lane_id=worktree.name,
        base="main" if target is None else target.base,
        path=worktree.path,
        pr=None if target is None else target.pr_url,
        spec=branch.slug,
    )
    if not _spec_record_exists(worktree.path, branch.slug):
        create_spec(
            branch.slug,
            schema=branch.spec_schema,
            description=f"Lane for {branch.branch}",
            cwd=worktree.path,
        )
    write_state(worktree.path, state)
    return state


def _resolve_attach_worktree(selector: str | None):
    if selector is None:
        worktrees = list_worktrees(cwd=Path.cwd())
        cwd = Path.cwd().resolve()
        matches = [
            worktree
            for worktree in worktrees
            if cwd == worktree.path.resolve() or worktree.path.resolve() in cwd.parents
        ]
        return _single_worktree_match(matches, "."), None

    candidate = Path(selector).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.exists():
        selected_path = candidate.resolve()
        worktrees = list_worktrees(cwd=selected_path)
        matches = [
            worktree
            for worktree in worktrees
            if selected_path == worktree.path.resolve()
            or worktree.path.resolve() in selected_path.parents
        ]
        return _single_worktree_match(matches, selector), None

    worktrees = list_worktrees(cwd=Path.cwd())
    local = _resolve_attach_local_selector(selector, worktrees)
    if local is not None:
        return local, None

    target = resolve_lane_target(selector, _known_lane_states(), cwd=Path.cwd())
    matches = [worktree for worktree in worktrees if worktree.branch == target.branch]
    return _single_worktree_match(matches, selector), target


def _resolve_attach_local_selector(selector: str, worktrees: list):
    if "/" in selector:
        matches = [worktree for worktree in worktrees if worktree.branch == selector]
    else:
        matches = [
            worktree
            for worktree in worktrees
            if worktree.name == selector
            or worktree.branch.rsplit("/", maxsplit=1)[-1] == selector
        ]
    try:
        return _single_worktree_match(matches, selector)
    except ValueError as error:
        if "ambiguous Paseo workspace selector" in str(error):
            raise
        return None


def _single_worktree_match(matches: list, selector: str):
    if not matches:
        raise ValueError(f"no Paseo workspace matches {selector!r}")
    if len(matches) > 1:
        candidates = ", ".join(sorted(worktree.branch for worktree in matches))
        raise ValueError(
            f"ambiguous Paseo workspace selector {selector!r}; candidates: {candidates}"
        )
    return matches[0]


def _spec_record_exists(workspace: Path, spec: str) -> bool:
    if active_spec_path(workspace, spec).exists():
        return True
    archive_dir = workspace / "openspec" / "changes" / "archive"
    if not archive_dir.exists():
        return False
    return any(
        path.is_dir() and (path.name == spec or path.name.endswith(f"-{spec}"))
        for path in archive_dir.iterdir()
    )


def _new_lane_state(
    *,
    branch: str,
    lane_id: str,
    base: str,
    path: Path,
    pr: str | None,
    spec: str | None = None,
) -> LaneState:
    return LaneState(
        schema=STATE_SCHEMA,
        id=lane_id,
        status="active",
        branch=branch,
        base=base,
        path=path,
        spec=lane_id if spec is None else spec,
        review="none",
        pr=pr,
    )


def _known_lane_states() -> list[LaneState]:
    lanes: list[LaneState] = []
    for worktree in list_worktrees(cwd=Path.cwd()):
        try:
            lanes.append(read_state(worktree.path))
        except FileNotFoundError:
            continue
    return lanes


if __name__ == "__main__":
    raise SystemExit(main())
