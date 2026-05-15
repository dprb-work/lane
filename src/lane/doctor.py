from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from lane.forge_remote import ForgeRemoteError, infer_forge_remote
from lane.paseo import PaseoError, list_worktrees
from lane.run import command_env
from lane.state import find_state_path, read_state
from lane.verify import VerifyError, discover_verify_command

DiagnosticStatus = Literal["ok", "warn", "fail"]


@dataclass(frozen=True)
class Diagnostic:
    status: DiagnosticStatus
    name: str
    detail: str


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        pass


def run_doctor(
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> tuple[Diagnostic, ...]:
    workspace = workspace.resolve()
    runner = _run if runner is None else runner
    return (
        _tool_check("git"),
        _paseo_check(workspace, runner),
        _paseo_daemon_check(workspace, runner),
        _tool_check("openspec"),
        _forge_check(workspace, runner),
        _verification_check(workspace),
        _lane_state_check(workspace),
    )


def has_failures(diagnostics: tuple[Diagnostic, ...]) -> bool:
    return any(diagnostic.status == "fail" for diagnostic in diagnostics)


def _tool_check(tool: str) -> Diagnostic:
    path = shutil.which(tool)
    if path is None:
        return Diagnostic("fail", tool, "not found on PATH")
    return Diagnostic("ok", tool, path)


def _paseo_check(workspace: Path, runner: Runner) -> Diagnostic:
    if shutil.which("paseo") is None:
        return Diagnostic("fail", "paseo", "not found on PATH")
    result = runner(["paseo", "--version"], workspace)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "version failed"
        return Diagnostic("fail", "paseo", message)
    version = result.stdout.strip() or result.stderr.strip()
    return Diagnostic("ok", "paseo", version or "version unknown")


def _paseo_daemon_check(workspace: Path, runner: Runner) -> Diagnostic:
    if shutil.which("paseo") is None:
        return Diagnostic("fail", "paseo daemon", "paseo not found on PATH")
    try:
        list_worktrees(cwd=workspace, runner=runner)
    except PaseoError as error:
        return Diagnostic("warn", "paseo daemon", str(error))
    return Diagnostic("ok", "paseo daemon", "worktree list available")


def _forge_check(workspace: Path, runner: Runner) -> Diagnostic:
    if shutil.which("git") is None:
        return Diagnostic("fail", "forge", "git not found on PATH")
    try:
        remote = infer_forge_remote(workspace, runner=runner)
    except ForgeRemoteError as error:
        return Diagnostic("warn", "forge", str(error))
    cli = "gh" if remote.provider == "github" else "glab"
    if shutil.which(cli) is None:
        return Diagnostic("fail", "forge", f"{remote.provider} remote requires {cli}")
    detail = f"{remote.provider} via {remote.name}: {remote.repo}"
    return Diagnostic("ok", "forge", detail)


def _verification_check(workspace: Path) -> Diagnostic:
    try:
        command = discover_verify_command(workspace)
    except VerifyError as error:
        return Diagnostic("warn", "verification", str(error))
    env = command_env(workspace)
    executable = command.argv[0]
    if shutil.which(executable, path=env.get("PATH")) is None:
        return Diagnostic(
            "fail",
            "verification",
            f"{command.label} requires {executable} on PATH",
        )
    return Diagnostic("ok", "verification", command.label)


def _lane_state_check(workspace: Path) -> Diagnostic:
    path = find_state_path(workspace)
    if path is None:
        return Diagnostic("warn", "lane state", "no .lane/state.yaml found")
    try:
        state = read_state(path.parent.parent)
    except Exception as error:
        return Diagnostic("fail", "lane state", str(error))
    return Diagnostic("ok", "lane state", f"{state.id} ({state.status})")


def _run(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
