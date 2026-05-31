from __future__ import annotations

import subprocess
from pathlib import Path

import lane.doctor as doctor
from lane.doctor import has_failures, run_doctor
from lane.state import LaneState, write_state


def test_run_doctor_reports_ok_diagnostics(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"verify":"ruff check . && pytest"}}',
        encoding="utf-8",
    )
    opencode_tool = tmp_path / "lane.ts"
    opencode_tool.write_text(
        str(Path(doctor.__file__).resolve().parents[2]),
        encoding="utf-8",
    )
    codex_skill = tmp_path / ".agents" / "skills" / "lane" / "SKILL.md"
    codex_skill.parent.mkdir(parents=True)
    codex_skill.write_text(doctor.CODEX_SKILL_MARKER, encoding="utf-8")
    write_state(tmp_path, _state(tmp_path))

    monkeypatch.setattr("lane.doctor.opencode_tool_path", lambda: opencode_tool)
    monkeypatch.setattr("lane.doctor.codex_skill_path", lambda: codex_skill)
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: f"/bin/{tool}",
    )

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        if argv == ["paseo", "--version"]:
            return _result(stdout="0.1.75\n")
        if argv == ["paseo", "worktree", "ls", "--json"]:
            return _result(stdout="[]")
        if argv == ["git", "remote", "-v"]:
            return _result(stdout="upstream\thttps://github.com/acme/app.git (fetch)\n")
        if argv == ["gh", "auth", "status"]:
            return _result(stdout="Logged in\n")
        if argv == ["gh", "repo", "view", "acme/app"]:
            return _result(stdout="acme/app\n")
        if argv == ["gh", "api", "repos/acme/app/rulesets"]:
            return _result(stdout="[]")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)

    assert not has_failures(diagnostics)
    assert ("ok", "paseo", "0.1.75") in _triples(diagnostics)
    assert ("ok", "forge", "github via upstream: acme/app") in _triples(diagnostics)
    assert ("ok", "forge auth", "gh auth available") in _triples(diagnostics)
    assert ("ok", "forge repo", "readable: acme/app") in _triples(diagnostics)
    assert ("ok", "forge rulesets", "readable") in _triples(diagnostics)
    assert any(
        status == "ok" and name == "opencode tool"
        for status, name, detail in _triples(diagnostics)
    )
    assert ("ok", "codex skill", str(codex_skill)) in _triples(diagnostics)
    assert ("ok", "verification", "npm run verify") in _triples(diagnostics)
    assert ("ok", "lane state", "login (active)") in _triples(diagnostics)


def test_run_doctor_reports_failures_and_warnings(tmp_path: Path, monkeypatch) -> None:
    def fake_which(tool: str, path: str | None = None) -> str | None:
        return "/bin/git" if tool == "git" else None

    monkeypatch.setattr("lane.doctor.shutil.which", fake_which)

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "remote", "-v"]:
            return _result(returncode=1, stderr="no remotes")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)
    triples = _triples(diagnostics)

    assert has_failures(diagnostics)
    assert ("fail", "paseo", "not found on PATH") in triples
    assert ("fail", "openspec", "not found on PATH") in triples
    assert (
        "warn",
        "verification",
        "no verify command found; add `just verify`, `scripts/verify.py`, "
        "or `npm run verify`",
    ) in triples
    assert ("warn", "lane state", "no .lane/state.yaml found") in triples


def test_run_doctor_warns_when_opencode_tool_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing = tmp_path / "tools" / "lane.ts"
    monkeypatch.setattr("lane.doctor.opencode_tool_path", lambda: missing)
    monkeypatch.setattr(
        "lane.doctor.compact_opencode_registration_note",
        lambda: "install opencode tool: lane install",
    )
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: "/bin/opencode" if tool == "opencode" else None,
    )

    diagnostics = run_doctor(tmp_path, runner=lambda argv, cwd: _result())

    assert (
        "warn",
        "opencode tool",
        "install opencode tool: lane install",
    ) in _triples(diagnostics)


def test_run_doctor_warns_when_codex_skill_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing = tmp_path / "SKILL.md"
    monkeypatch.setattr("lane.doctor.codex_skill_path", lambda: missing)
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: "/bin/codex" if tool == "codex" else None,
    )

    diagnostics = run_doctor(tmp_path, runner=lambda argv, cwd: _result())

    assert (
        "warn",
        "codex skill",
        "install codex skill: lane install",
    ) in _triples(diagnostics)


def test_run_doctor_warns_for_custom_codex_skill(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill = tmp_path / ".agents" / "skills" / "lane" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: lane\n---\ncustom\n", encoding="utf-8")
    monkeypatch.setattr("lane.doctor.codex_skill_path", lambda: skill)
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: "/bin/codex" if tool == "codex" else None,
    )

    diagnostics = run_doctor(tmp_path, runner=lambda argv, cwd: _result())

    assert (
        "warn",
        "codex skill",
        f"custom skill not managed by lane: {skill}",
    ) in _triples(diagnostics)


def test_run_doctor_reports_global_codex_skill_from_subdirectory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill = tmp_path / ".agents" / "skills" / "lane" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(doctor.CODEX_SKILL_MARKER, encoding="utf-8")
    subdirectory = tmp_path / "src" / "pkg"
    subdirectory.mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("lane.doctor.codex_skill_path", lambda: skill)
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: "/bin/codex" if tool == "codex" else None,
    )

    diagnostics = run_doctor(subdirectory, runner=lambda argv, cwd: _result())

    assert ("ok", "codex skill", str(skill)) in _triples(diagnostics)


def test_run_doctor_skips_optional_agent_integrations_when_cli_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("lane.doctor.shutil.which", lambda tool, path=None: None)

    diagnostics = run_doctor(tmp_path, runner=lambda argv, cwd: _result())
    triples = _triples(diagnostics)

    assert (
        "ok",
        "opencode tool",
        "opencode tool skipped: opencode not found on PATH",
    ) in triples
    assert (
        "ok",
        "codex skill",
        "codex skill skipped: codex not found on PATH",
    ) in triples


def test_run_doctor_reports_registered_opencode_tool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = tmp_path / "lane.ts"
    tool.write_text(str(Path(doctor.__file__).resolve().parents[2]), encoding="utf-8")
    monkeypatch.setattr("lane.doctor.opencode_tool_path", lambda: tool)
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: "/bin/opencode" if tool == "opencode" else None,
    )

    diagnostics = run_doctor(tmp_path, runner=lambda argv, cwd: _result())

    assert ("ok", "opencode tool", str(tool)) in _triples(diagnostics)


def test_run_doctor_warns_for_stale_opencode_tool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = tmp_path / "lane.ts"
    tool.write_text("const REPO_ROOT = '/other/checkout';", encoding="utf-8")
    monkeypatch.setattr("lane.doctor.opencode_tool_path", lambda: tool)
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: "/bin/opencode" if tool == "opencode" else None,
    )

    diagnostics = run_doctor(tmp_path, runner=lambda argv, cwd: _result())

    assert (
        "warn",
        "opencode tool",
        f"registered to another checkout or install: {tool}",
    ) in _triples(diagnostics)


def test_run_doctor_reports_github_auth_and_repo_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: f"/bin/{tool}",
    )

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        if argv == ["paseo", "--version"]:
            return _result(stdout="0.1.75\n")
        if argv == ["paseo", "worktree", "ls", "--json"]:
            return _result(stdout="[]")
        if argv == ["git", "remote", "-v"]:
            return _result(stdout="origin\thttps://github.com/acme/app.git (fetch)\n")
        if argv == ["gh", "auth", "status"]:
            return _result(returncode=1, stderr="not logged in")
        if argv == ["gh", "repo", "view", "acme/app"]:
            return _result(returncode=1, stderr="HTTP 404")
        if argv == ["gh", "api", "repos/acme/app/rulesets"]:
            return _result(returncode=1, stderr="HTTP 403")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)
    triples = _triples(diagnostics)

    assert has_failures(diagnostics)
    assert ("fail", "forge auth", "not logged in") in triples
    assert ("fail", "forge repo", "HTTP 404") in triples
    assert ("warn", "forge rulesets", "HTTP 403") in triples


def test_run_doctor_reports_gitlab_auth_and_repo_readiness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: f"/bin/{tool}",
    )

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        if argv == ["paseo", "--version"]:
            return _result(stdout="0.1.75\n")
        if argv == ["paseo", "worktree", "ls", "--json"]:
            return _result(stdout="[]")
        if argv == ["git", "remote", "-v"]:
            return _result(stdout="origin\thttps://gitlab.com/acme/app.git (fetch)\n")
        if argv == ["glab", "auth", "status", "--hostname", "gitlab.com"]:
            return _result(stdout="Logged in\n")
        if argv == ["glab", "repo", "view", "acme/app"]:
            return _result(stdout="acme/app\n")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)

    assert ("ok", "forge", "gitlab via origin: acme/app") in _triples(diagnostics)
    assert ("ok", "forge auth", "glab auth available") in _triples(diagnostics)
    assert ("ok", "forge repo", "readable: acme/app") in _triples(diagnostics)


def test_run_doctor_targets_self_hosted_gitlab_remote(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: f"/bin/{tool}",
    )
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["paseo", "--version"]:
            return _result(stdout="0.1.75\n")
        if argv == ["paseo", "worktree", "ls", "--json"]:
            return _result(stdout="[]")
        if argv == ["git", "remote", "-v"]:
            return _result(
                stdout="origin\tgit@gitlab.example.com:acme/group/app.git (fetch)\n"
            )
        if argv == ["glab", "auth", "status", "--hostname", "gitlab.example.com"]:
            return _result(stdout="Logged in\n")
        if argv == [
            "glab",
            "repo",
            "view",
            "https://gitlab.example.com/acme/group/app",
        ]:
            return _result(stdout="acme/group/app\n")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)

    assert not has_failures(diagnostics)
    assert ("ok", "forge", "gitlab via origin: acme/group/app") in _triples(
        diagnostics
    )
    assert ["glab", "auth", "status", "--hostname", "gitlab.example.com"] in calls
    assert [
        "glab",
        "repo",
        "view",
        "https://gitlab.example.com/acme/group/app",
    ] in calls


def test_run_doctor_preserves_self_hosted_gitlab_https_port(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: f"/bin/{tool}",
    )
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["paseo", "--version"]:
            return _result(stdout="0.1.75\n")
        if argv == ["paseo", "worktree", "ls", "--json"]:
            return _result(stdout="[]")
        if argv == ["git", "remote", "-v"]:
            return _result(
                stdout="origin\thttps://gitlab.example.com:8443/acme/app.git (fetch)\n"
            )
        if argv == ["glab", "auth", "status", "--hostname", "gitlab.example.com:8443"]:
            return _result(stdout="Logged in\n")
        if argv == [
            "glab",
            "repo",
            "view",
            "https://gitlab.example.com:8443/acme/app",
        ]:
            return _result(stdout="acme/app\n")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)

    assert not has_failures(diagnostics)
    assert ["glab", "auth", "status", "--hostname", "gitlab.example.com:8443"] in calls
    assert [
        "glab",
        "repo",
        "view",
        "https://gitlab.example.com:8443/acme/app",
    ] in calls


def test_run_doctor_rejects_invalid_lane_state_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_state(tmp_path, _state(tmp_path, branch="task/login"))
    monkeypatch.setattr(
        "lane.doctor.shutil.which",
        lambda tool, path=None: f"/bin/{tool}",
    )

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        if argv == ["paseo", "--version"]:
            return _result(stdout="0.1.75\n")
        if argv == ["paseo", "worktree", "ls", "--json"]:
            return _result(stdout="[]")
        if argv == ["git", "remote", "-v"]:
            return _result(stdout="origin\thttps://github.com/acme/app.git (fetch)\n")
        if argv in (
            ["gh", "auth", "status"],
            ["gh", "repo", "view", "acme/app"],
            ["gh", "api", "repos/acme/app/rulesets"],
        ):
            return _result(stdout="ok")
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)

    assert has_failures(diagnostics)
    assert any(
        status == "fail"
        and name == "lane state"
        and "unsupported branch type 'task'" in detail
        for status, name, detail in _triples(diagnostics)
    )


def _state(path: Path, *, branch: str = "fix/login") -> LaneState:
    return LaneState(
        schema=1,
        id="login",
        status="active",
        branch=branch,
        base="main",
        path=path,
        spec="login",
        review="none",
        pr=None,
    )


def _triples(diagnostics):
    return [(item.status, item.name, item.detail) for item in diagnostics]


def _result(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)
