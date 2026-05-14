from __future__ import annotations

from pathlib import Path

from lane.selectors import pr_number
from lane.state import LaneState, find_state_path, read_state


def resolve_current_directory(start: Path) -> LaneState:
    path = find_state_path(start)
    if path is None:
        raise ValueError("no .lane/state.yaml found from current directory")
    return read_state(path.parent.parent)


def resolve_filesystem_path(selector: str, *, cwd: Path | None = None) -> LaneState:
    path = Path(selector).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() if cwd is None else cwd) / path
    if not path.exists():
        raise ValueError(f"path does not exist: {selector!r}")

    state_path = find_state_path(path)
    if state_path is None:
        raise ValueError(f"no .lane/state.yaml found from path {selector!r}")
    return read_state(state_path.parent.parent)


def resolve_exact_branch(branch: str, lanes: list[LaneState]) -> LaneState:
    matches = [lane for lane in lanes if lane.branch == branch]
    return _single_match(matches, branch)


def resolve_slug(slug: str, lanes: list[LaneState]) -> LaneState:
    matches = [lane for lane in lanes if lane.id == slug or lane.spec == slug]
    return _single_match(matches, slug)


def resolve_pr_selector(selector: str, lanes: list[LaneState]) -> LaneState:
    selector_pr_number = pr_number(selector)
    if selector_pr_number is None:
        raise ValueError(f"not a PR selector: {selector!r}")

    matches = [
        lane
        for lane in lanes
        if lane.pr is not None
        and (lane.pr == selector or pr_number(lane.pr) == selector_pr_number)
    ]
    return _single_match(matches, selector)


def _single_match(matches: list[LaneState], selector: str) -> LaneState:
    if not matches:
        raise ValueError(f"no lane matches {selector!r}")
    if len(matches) > 1:
        candidates = ", ".join(sorted(lane.branch for lane in matches))
        raise ValueError(
            f"ambiguous lane selector {selector!r}; candidates: {candidates}"
        )
    return matches[0]
