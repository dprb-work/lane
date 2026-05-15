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
    calls: list[tuple[str, str | None, str, Path]] = []

    def fake_create_worktree(
        branch: str,
        *,
        base: str,
        cwd: Path,
        worktree_slug: str | None = None,
    ) -> PaseoWorktree:
        calls.append((branch, worktree_slug, base, cwd))
        return PaseoWorktree(name="login", branch="login", path=workspace)

    renamed: list[tuple[str, Path]] = []

    def fake_rename_current_branch(branch: str, *, cwd: Path) -> None:
        renamed.append((branch, cwd))

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
    monkeypatch.setattr(cli, "rename_current_branch", fake_rename_current_branch)
    monkeypatch.setattr(cli, "create_spec", fake_create_spec)

    assert cli.main(["start", "fix/login", "--base", "main"]) == 0

    assert calls == [("fix/login", "login", "main", tmp_path)]
    assert renamed == [("fix/login", workspace)]
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

    def fake_create_worktree(
        branch: str,
        *,
        base: str,
        cwd: Path,
        worktree_slug: str | None = None,
    ) -> PaseoWorktree:
        return PaseoWorktree(name="login", branch=branch, path=workspace)

    def fake_create_spec(
        name: str,
        *,
        schema: str,
        description: str,
        cwd: Path,
    ) -> None:
        raise OpenSpecError("spec failed")

    archived: list[str] = []

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        archived.append(name)
        return PaseoArchiveResult(name="login", removed_agents=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "create_worktree", fake_create_worktree)
    monkeypatch.setattr(cli, "create_spec", fake_create_spec)
    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)

    assert cli.main(["start", "fix/login"]) == 2
    assert not (workspace / ".lane" / "state.yaml").exists()
    assert archived == ["login"]


def test_start_rolls_back_when_branch_rename_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"

    def fake_create_worktree(
        branch: str,
        *,
        base: str,
        cwd: Path,
        worktree_slug: str | None = None,
    ) -> PaseoWorktree:
        return PaseoWorktree(name="login", branch="login", path=workspace)

    archived: list[str] = []

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        archived.append(name)
        return PaseoArchiveResult(name="login", removed_agents=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "create_worktree", fake_create_worktree)
    monkeypatch.setattr(
        cli,
        "rename_current_branch",
        lambda branch, *, cwd: (_ for _ in ()).throw(
            cli.PaseoError("rename failed")
        ),
    )
    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)

    assert cli.main(["start", "fix/login"]) == 2
    assert not (workspace / ".lane" / "state.yaml").exists()
    assert archived == ["login"]


def test_start_reports_rollback_failure_when_spec_creation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"

    def fake_create_worktree(
        branch: str,
        *,
        base: str,
        cwd: Path,
        worktree_slug: str | None = None,
    ) -> PaseoWorktree:
        return PaseoWorktree(name="login", branch=branch, path=workspace)

    def fake_create_spec(
        name: str,
        *,
        schema: str,
        description: str,
        cwd: Path,
    ) -> None:
        raise OpenSpecError("spec failed")

    def fake_archive_worktree(name: str) -> PaseoArchiveResult:
        raise cli.PaseoError("archive failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "create_worktree", fake_create_worktree)
    monkeypatch.setattr(cli, "create_spec", fake_create_spec)
    monkeypatch.setattr(cli, "archive_worktree", fake_archive_worktree)

    assert cli.main(["start", "fix/login"]) == 2
    assert not (workspace / ".lane" / "state.yaml").exists()


def test_attach_current_paseo_workspace_writes_state_and_creates_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    spec_calls: list[tuple[str, str, str, Path]] = []

    def fake_create_spec(
        name: str,
        *,
        schema: str,
        description: str,
        cwd: Path,
    ) -> None:
        spec_calls.append((name, schema, description, cwd))

    monkeypatch.chdir(workspace)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )
    monkeypatch.setattr(cli, "create_spec", fake_create_spec)

    assert cli.main(["attach"]) == 0

    state = read_state(workspace)
    assert state.id == "login"
    assert state.branch == "fix/login"
    assert state.base == "main"
    assert state.path == workspace
    assert state.spec == "login"
    assert spec_calls == [
        ("login", "lane-lite", "Lane for fix/login", workspace),
    ]


def test_attach_existing_state_is_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    state = _state(workspace, branch="fix/login")
    write_state(workspace, state)
    spec_calls: list[str] = []

    monkeypatch.chdir(workspace)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: spec_calls.append(name),
    )

    assert cli.main(["attach"]) == 0

    assert read_state(workspace) == state
    assert spec_calls == []


def test_attach_path_selector_lists_from_selected_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    outside = tmp_path / "outside"
    workspace = tmp_path / "workspace"
    outside.mkdir()
    workspace.mkdir()

    def fake_list_worktrees(*, cwd: Path):
        if cwd != workspace:
            raise cli.PaseoError(f"unexpected cwd: {cwd}")
        return [PaseoWorktree(name="login", branch="fix/login", path=workspace)]

    monkeypatch.chdir(outside)
    monkeypatch.setattr(cli, "list_worktrees", fake_list_worktrees)
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: None,
    )

    assert cli.main(["attach", str(workspace)]) == 0

    state = read_state(workspace)
    assert state.id == "login"
    assert state.branch == "fix/login"


def test_attach_branch_selector_preserves_existing_active_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "openspec" / "changes" / "login").mkdir(parents=True)
    spec_calls: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: spec_calls.append(name),
    )

    assert cli.main(["attach", "fix/login"]) == 0

    state = read_state(workspace)
    assert state.id == "login"
    assert state.branch == "fix/login"
    assert state.spec == "login"
    assert spec_calls == []


def test_attach_pr_selector_records_provider_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: None,
    )
    monkeypatch.setattr(
        cli,
        "resolve_lane_target",
        lambda selector, lanes, *, cwd: cli.LaneTarget(
            selector=selector,
            branch="fix/login",
            base="release",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )

    assert cli.main(["attach", "#123"]) == 0

    state = read_state(workspace)
    assert state.base == "release"
    assert state.pr == "https://github.com/acme/app/pull/123"


def test_attach_refuses_ambiguous_slug(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [
            PaseoWorktree(name="login-a", branch="fix/login", path=tmp_path / "one"),
            PaseoWorktree(name="login-b", branch="feat/login", path=tmp_path / "two"),
        ],
    )

    assert cli.main(["attach", "login"]) == 2


def test_cleanup_archives_resolved_lane_worktree_name(
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
    assert calls == ["login"]


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


def test_abort_archives_explicit_path_lane_worktree_name(
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
    assert calls == ["drop-experiment"]


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
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
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
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
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
        lambda **_: [PaseoWorktree(name="login", branch="fix/login", path=workspace)],
    )

    assert cli.main(["status", "#123"]) == 0


def test_status_materializes_remote_lane_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    spec_calls: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "list_worktrees", lambda **_: [])
    monkeypatch.setattr(
        cli,
        "checkout_branch_worktree",
        lambda branch, *, cwd: PaseoWorktree(
            name="login-review", branch=branch, path=workspace
        ),
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: spec_calls.append(name),
    )
    monkeypatch.setattr(
        cli,
        "resolve_lane_target",
        lambda selector, lanes, *, cwd: cli.LaneTarget(
            selector=selector,
            branch="fix/login",
            base="release",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )

    assert cli.main(["status", "#123"]) == 0
    state = read_state(workspace)
    assert state.id == "login-review"
    assert state.branch == "fix/login"
    assert state.base == "release"
    assert state.spec == "login"
    assert state.pr == "https://github.com/acme/app/pull/123"
    assert spec_calls == []


def test_status_materialization_preserves_existing_active_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "openspec" / "changes" / "login").mkdir(parents=True)
    spec_calls: list[str] = []
    archive_calls: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "list_worktrees", lambda **_: [])
    monkeypatch.setattr(
        cli,
        "checkout_branch_worktree",
        lambda branch, *, cwd: PaseoWorktree(
            name="login-review", branch=branch, path=workspace
        ),
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: spec_calls.append(name),
    )
    monkeypatch.setattr(
        cli,
        "archive_worktree",
        lambda name: archive_calls.append(name)
        or PaseoArchiveResult(name=name, removed_agents=()),
    )
    monkeypatch.setattr(
        cli,
        "resolve_lane_target",
        lambda selector, lanes, *, cwd: cli.LaneTarget(
            selector=selector,
            branch="fix/login",
            base="main",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )

    assert cli.main(["status", "#123"]) == 0

    state = read_state(workspace)
    assert state.id == "login-review"
    assert state.branch == "fix/login"
    assert state.spec == "login"
    assert spec_calls == []
    assert archive_calls == []


def test_finalize_materialized_remote_lane_does_not_recreate_archived_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    spec_calls: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "list_worktrees", lambda **_: [])
    monkeypatch.setattr(
        cli,
        "checkout_branch_worktree",
        lambda branch, *, cwd: PaseoWorktree(
            name="login-review", branch=branch, path=workspace
        ),
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: spec_calls.append(name),
    )
    monkeypatch.setattr(
        cli,
        "resolve_lane_target",
        lambda selector, lanes, *, cwd: cli.LaneTarget(
            selector=selector,
            branch="fix/login",
            base="main",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )
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

    assert cli.main(["finalize", "#123"]) == 0

    state = read_state(workspace)
    assert state.id == "login-review"
    assert state.spec == "login"
    assert state.status == "finalized"
    assert spec_calls == []


def test_cleanup_materialized_remote_lane_does_not_recreate_archived_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    spec_calls: list[str] = []
    archive_calls: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "list_worktrees", lambda **_: [])
    monkeypatch.setattr(
        cli,
        "checkout_branch_worktree",
        lambda branch, *, cwd: PaseoWorktree(
            name="login-review", branch=branch, path=workspace
        ),
    )
    monkeypatch.setattr(
        cli,
        "create_spec",
        lambda name, *, schema, description, cwd: spec_calls.append(name),
    )
    monkeypatch.setattr(
        cli,
        "resolve_lane_target",
        lambda selector, lanes, *, cwd: cli.LaneTarget(
            selector=selector,
            branch="fix/login",
            base="main",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )
    monkeypatch.setattr(cli, "ensure_pr_merged", lambda pr_url, workspace: None)
    monkeypatch.setattr(
        cli,
        "archive_worktree",
        lambda name: archive_calls.append(name)
        or PaseoArchiveResult(name=name, removed_agents=()),
    )

    assert cli.main(["cleanup", "#123"]) == 0

    assert spec_calls == []
    assert archive_calls == ["login-review"]


def test_abort_materialized_remote_lane_archives_paseo_worktree_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    archive_calls: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "list_worktrees", lambda **_: [])
    monkeypatch.setattr(
        cli,
        "checkout_branch_worktree",
        lambda branch, *, cwd: PaseoWorktree(
            name="login-review", branch=branch, path=workspace
        ),
    )
    monkeypatch.setattr(
        cli,
        "resolve_lane_target",
        lambda selector, lanes, *, cwd: cli.LaneTarget(
            selector=selector,
            branch="fix/login",
            base="main",
            pr_url="https://github.com/acme/app/pull/123",
        ),
    )
    monkeypatch.setattr(
        cli,
        "ensure_clean_worktree",
        lambda workspace, *, allow_dirty: None,
    )
    monkeypatch.setattr(
        cli,
        "archive_worktree",
        lambda name: archive_calls.append(name)
        or PaseoArchiveResult(name=name, removed_agents=()),
    )

    assert cli.main(["abort", "#123"]) == 0

    state = read_state(workspace)
    assert state.id == "login-review"
    assert state.spec == "login"
    assert archive_calls == ["login-review"]


def test_list_prints_known_lanes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_state(first, _state(first, branch="fix/login"))
    write_state(
        second,
        _state(
            second,
            branch="feat/dashboard",
            pr="https://github.com/acme/app/pull/123",
        ),
    )
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [
            PaseoWorktree(name="dashboard", branch="feat/dashboard", path=second),
            PaseoWorktree(name="login", branch="fix/login", path=first),
        ],
    )

    assert cli.main(["list"]) == 0

    lines = capsys.readouterr().out.splitlines()

    assert lines == [
        (
            "ID         STATUS  BRANCH          REVIEW  PR"
            "                                    PATH"
        ),
        (
            "dashboard  active  feat/dashboard  none    "
            f"https://github.com/acme/app/pull/123  {second}"
        ),
        (
            "login      active  fix/login       none    -"
            f"                                     {first}"
        ),
    ]


def test_list_skips_worktrees_without_lane_state(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(
        cli,
        "list_worktrees",
        lambda **_: [
            PaseoWorktree(name="external", branch="fix/external", path=workspace)
        ],
    )

    assert cli.main(["list"]) == 0

    assert capsys.readouterr().out == "ID  STATUS  BRANCH  REVIEW  PR  PATH\n"


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
    lane_id = branch.split("/", maxsplit=1)[1]
    return LaneState(
        schema=1,
        id=lane_id,
        status="active",
        branch=branch,
        base="main",
        path=path,
        spec=lane_id,
        review="none",
        pr=pr,
    )
