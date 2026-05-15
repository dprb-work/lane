from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RunError(RuntimeError):
    pass


@dataclass(frozen=True)
class LaneCommandResult:
    argv: list[str]
    exit_status: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        *,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[str]:
        pass


def command_env(
    workspace: Path,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    venv = workspace / ".venv"
    venv_bin = venv / "bin"
    if not venv_bin.is_dir():
        return env

    env["VIRTUAL_ENV"] = str(venv)
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env.pop("PYTHONHOME", None)
    return env


def run_lane_command(
    workspace: Path,
    argv: list[str],
    *,
    capture_output: bool,
    runner: Runner | None = None,
) -> LaneCommandResult:
    if not argv:
        raise RunError("missing command after `--`")

    runner = _run if runner is None else runner
    try:
        result = runner(
            argv,
            workspace,
            command_env(workspace),
            capture_output=capture_output,
        )
    except FileNotFoundError as error:
        raise RunError(f"command not found: {argv[0]}") from error

    return LaneCommandResult(
        argv=argv,
        exit_status=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def _run(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=capture_output,
    )
