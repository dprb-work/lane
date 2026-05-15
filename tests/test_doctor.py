from __future__ import annotations

import subprocess
from pathlib import Path

from lane.doctor import has_failures, run_doctor
from lane.state import LaneState, write_state


def test_run_doctor_reports_ok_diagnostics(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"verify":"ruff check . && pytest"}}',
        encoding="utf-8",
    )
    write_state(tmp_path, _state(tmp_path))

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
        raise AssertionError(argv)

    diagnostics = run_doctor(tmp_path, runner=runner)

    assert not has_failures(diagnostics)
    assert ("ok", "paseo", "0.1.75") in _triples(diagnostics)
    assert ("ok", "forge", "github via upstream: acme/app") in _triples(diagnostics)
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
        "no verify command found; add `just verify` or `npm run verify`",
    ) in triples
    assert ("warn", "lane state", "no .lane/state.yaml found") in triples


def _state(path: Path) -> LaneState:
    return LaneState(
        schema=1,
        id="login",
        status="active",
        branch="fix/login",
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
