from __future__ import annotations

from pathlib import Path

from lane import cli
from lane.forge import ForgeResult
from lane.openspec import OpenSpecError
from lane.paseo import PaseoArchiveResult, PaseoWorktree
from lane.state import LaneState, read_state, write_state
from lane.verify import VerifyCommand, VerifyResult


def test_start_uses_paseo_create_and_writes_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    calls: list[tuple[str, str, Path]] = []

    def fake_create_worktree(branch: str, *, base: str, cwd: Path) -> PaseoWorktree:
        calls.append((branch, base, cwd))
        return PaseoWorktree(name="login", branch=branch, path=workspace)

    spec_calls: list[tuple[str, str, str, Path]] = []

    def fake_create_spec(
        name: str,
        *,
        schema: str,
        description: str,
        cwd: Path,
    ) -> None:
        spec_calls.append((name, schema, description, cwd))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "create_worktree", fake_create_worktree)
    monkeypatch.setattr(cli, "create_spec", fake_create_spec)

    assert cli.main(["start", "fix/login", "--base", "main"]) == 0

    assert calls == [("fix/login", "main", tmp_path)]
    state = read_state(workspace)
    assert state.id == "login"
    assert state.branch == "fix/login"
    assert state.base == "main"
    assert state.path == workspace
    assert state.spec == "login"
    assert spec_calls == [
        ("login", "lane-lite", "Lane for fix/login", workspace),
    ]


def test_start_does_not_write_state_when_spec_creation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"

    def fake_create_worktree(branch: str, *, base: str, cwd: Path) -> PaseoWorktree:
        return PaseoWorktree(name="login", branch=branch, path=workspace)

    def fake_create_spec(
        name: str,
        *,
        schema: str,
        description: str,
        cwd: Path,
    ) -> None:
        raise OpenSpecError("spec failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "create_worktree", fake_create_worktree)
    monkeypatch.setattr(cli, "create_spec", fake_create_spec)

    assert cli.main(["start", "fix/login"]) == 2
    assert not (workspace / ".lane" / "state.yaml").exists()


def test_cleanup_archives_resolved_lane_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(
        tmp_path,
        branch="fix/login",
        pr="https://github.com/acme/app/pull/123",
    )
    write_state(tmp_path, state)
    calls: list[str] = []

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        calls.append(name)
        return PaseoArchiveResult(name="login", removed_agents=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)
    monkeypatch.setattr(cli, "ensure_pr_merged", lambda pr_url, workspace: None)

    assert cli.main(["cleanup"]) == 0
    assert calls == ["fix/login"]


def test_cleanup_refuses_lane_without_pr(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(tmp_path, branch="fix/login")
    write_state(tmp_path, state)
    calls: list[str] = []

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        calls.append(name)
        return PaseoArchiveResult(name="login", removed_agents=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)

    assert cli.main(["cleanup"]) == 2
    assert calls == []


def test_cleanup_refuses_active_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(tmp_path, branch="fix/login")
    write_state(tmp_path, state)
    (tmp_path / "openspec" / "changes" / state.spec).mkdir(parents=True)
    calls: list[str] = []

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        calls.append(name)
        return PaseoArchiveResult(name="login", removed_agents=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)
    monkeypatch.setattr(cli, "ensure_pr_merged", lambda pr_url, workspace: None)

    assert cli.main(["cleanup"]) == 2
    assert calls == []


def test_abort_archives_explicit_path_lane_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    state = _state(workspace, branch="chore/drop-experiment")
    write_state(workspace, state)
    calls: list[str] = []

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        calls.append(name)
        return PaseoArchiveResult(name="drop-experiment", removed_agents=())

    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)
    monkeypatch.setattr(
        cli,
        "ensure_clean_worktree",
        lambda workspace, *, allow_dirty: None,
    )

    assert cli.main(["abort", str(workspace)]) == 0
    assert calls == ["chore/drop-experiment"]


def test_status_resolves_exact_branch_from_known_lanes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    state = _state(workspace, branch="fix/login")
    write_state(workspace, state)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )

    assert cli.main(["status", "fix/login"]) == 0


def test_status_resolves_slug_from_known_lanes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    state = _state(workspace, branch="fix/login")
    write_state(workspace, state)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )

    assert cli.main(["status", "login"]) == 0


def test_status_resolves_pr_selector_from_known_lanes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    state = _state(
        workspace,
        branch="fix/login",
        pr="https://github.com/acme/app/pull/123",
    )
    write_state(workspace, state)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )

    assert cli.main(["status", "#123"]) == 0


def test_finalize_refuses_active_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(tmp_path, branch="fix/login")
    write_state(tmp_path, state)
    (tmp_path / "openspec" / "changes" / state.spec).mkdir(parents=True)

    monkeypatch.chdir(tmp_path)

    assert cli.main(["finalize"]) == 2


def test_finalize_updates_state_with_pr_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(tmp_path, branch="fix/login")
    write_state(tmp_path, state)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "require_spec_archived", lambda workspace, spec: None)
    monkeypatch.setattr(
        cli,
        "run_verify",
        lambda workspace: VerifyResult(
            command=VerifyCommand(argv=["just", "verify"], label="just verify"),
            exit_status=0,
            summary="ok",
        ),
    )
    monkeypatch.setattr(
        cli,
        "finalize_pr",
        lambda state, verification: ForgeResult(
            repo="acme/app",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )

    assert cli.main(["finalize"]) == 0
    updated = read_state(tmp_path)
    assert updated.status == "finalized"
    assert updated.pr == "https://github.com/acme/app/pull/123"


def _state(path: Path, *, branch: str, pr: str | None = None) -> LaneState:
    return LaneState(
        schema=1,
        id=branch.split("/", maxsplit=1)[1],
        status="active",
        branch=branch,
        base="main",
        path=path,
        spec=branch.split("/", maxsplit=1)[1],
        review="none",
        pr=pr,
    )
