from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from lane.run import RunError, command_env, run_lane_command


def test_command_env_activates_workspace_venv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("PYTHONHOME", "/pythonhome")

    env = command_env(tmp_path)

    assert env["VIRTUAL_ENV"] == str(tmp_path / ".venv")
    assert env["PATH"].split(os.pathsep)[0] == str(venv_bin)
    assert "PYTHONHOME" not in env


def test_command_env_leaves_env_when_venv_missing(tmp_path: Path) -> None:
    env = command_env(tmp_path, {"PATH": "/usr/bin", "PYTHONHOME": "/pythonhome"})

    assert env == {"PATH": "/usr/bin", "PYTHONHOME": "/pythonhome"}


def test_run_lane_command_passes_workspace_argv_and_env(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    calls: list[tuple[list[str], Path, dict[str, str], bool]] = []

    def runner(
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        *,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd, env, capture_output))
        return subprocess.CompletedProcess(argv, 7, "out", "err")

    result = run_lane_command(
        tmp_path,
        ["python", "-m", "pytest"],
        capture_output=True,
        runner=runner,
    )

    assert result.exit_status == 7
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert calls[0][0] == ["python", "-m", "pytest"]
    assert calls[0][1] == tmp_path
    assert calls[0][2]["VIRTUAL_ENV"] == str(tmp_path / ".venv")
    assert calls[0][3] is True


def test_run_lane_command_rejects_missing_argv(tmp_path: Path) -> None:
    with pytest.raises(RunError, match="missing command"):
        run_lane_command(tmp_path, [], capture_output=False)
