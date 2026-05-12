from __future__ import annotations

from pathlib import Path

import pytest

from lane.resolve import (
    resolve_current_directory,
    resolve_exact_branch,
    resolve_filesystem_path,
    resolve_pr_selector,
    resolve_slug,
)
from lane.state import LaneState, write_state


def test_resolve_current_directory_reads_nearest_lane_state(tmp_path: Path) -> None:
    state = _state(tmp_path)
    write_state(tmp_path, state)

    assert resolve_current_directory(tmp_path / "child") == state


def test_resolve_filesystem_path_accepts_workspace_path(tmp_path: Path) -> None:
    state = _state(tmp_path)
    write_state(tmp_path, state)

    child = tmp_path / "src" / "lane"
    child.mkdir(parents=True)

    assert resolve_filesystem_path(str(child)) == state


def test_resolve_filesystem_path_accepts_relative_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    state = _state(workspace)
    write_state(workspace, state)


    assert resolve_filesystem_path("workspace", cwd=tmp_path) == state


def test_resolve_filesystem_path_rejects_missing_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no .lane/state.yaml found"):
        resolve_filesystem_path(str(tmp_path))


def test_resolve_filesystem_path_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path does not exist"):
        resolve_filesystem_path("missing", cwd=tmp_path)


def test_resolve_exact_branch_matches_known_lane(tmp_path: Path) -> None:
    state = _state(tmp_path, branch="fix/login-redirect")

    assert resolve_exact_branch("fix/login-redirect", [state]) == state


def test_resolve_slug_matches_known_lane_id(tmp_path: Path) -> None:
    state = _state(tmp_path, lane_id="login-redirect")

    assert resolve_slug("login-redirect", [state]) == state


def test_resolve_slug_matches_known_lane_spec(tmp_path: Path) -> None:
    state = _state(tmp_path, lane_id="login", spec="login-redirect")

    assert resolve_slug("login-redirect", [state]) == state


def test_resolve_known_lane_rejects_missing_match() -> None:
    with pytest.raises(ValueError, match="no lane matches"):
        resolve_exact_branch("fix/missing", [])


def test_resolve_known_lane_rejects_ambiguous_match(tmp_path: Path) -> None:
    first = _state(tmp_path / "first", lane_id="login", branch="fix/login")
    second = _state(tmp_path / "second", lane_id="login", branch="chore/login")

    with pytest.raises(ValueError, match="ambiguous lane selector"):
        resolve_slug("login", [first, second])


def test_resolve_pr_selector_matches_pr_number(tmp_path: Path) -> None:
    state = _state(tmp_path, pr="https://github.com/acme/app/pull/123")

    assert resolve_pr_selector("#123", [state]) == state


def test_resolve_pr_selector_matches_pr_url(tmp_path: Path) -> None:
    state = _state(tmp_path, pr="https://github.com/acme/app/pull/123")

    assert resolve_pr_selector("https://github.com/acme/app/pull/123", [state]) == state


def test_resolve_pr_selector_matches_gitlab_mr_url(tmp_path: Path) -> None:
    state = _state(tmp_path, pr="https://gitlab.com/acme/app/-/merge_requests/123")

    assert (
        resolve_pr_selector("https://gitlab.com/acme/app/-/merge_requests/123", [state])
        == state
    )


def test_resolve_pr_selector_rejects_non_pr_selector() -> None:
    with pytest.raises(ValueError, match="not a PR selector"):
        resolve_pr_selector("123", [])


def test_resolve_pr_selector_rejects_missing_match() -> None:
    with pytest.raises(ValueError, match="no lane matches"):
        resolve_pr_selector("#123", [])


def _state(
    path: Path,
    *,
    lane_id: str = "login-redirect",
    branch: str = "fix/login-redirect",
    spec: str = "login-redirect",
    pr: str | None = None,
) -> LaneState:
    return LaneState(
        schema=1,
        id=lane_id,
        status="active",
        branch=branch,
        base="main",
        path=path,
        spec=spec,
        review="none",
        pr=pr,
    )
