from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from lane.branches import parse_branch
from lane.forge_remote import ForgeRemote, ForgeRemoteError, infer_forge_remote
from lane.init import compact_opencode_registration_note, opencode_tool_path
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
        _opencode_tool_check(),
        *_forge_checks(workspace, runner),
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


def _opencode_tool_check() -> Diagnostic:
    path = opencode_tool_path()
    if not path.is_file():
        return Diagnostic("warn", "opencode tool", compact_opencode_registration_note())
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        return Diagnostic("warn", "opencode tool", str(error))
    if "__LANE_REPO_ROOT__" in content:
        return Diagnostic(
            "warn",
            "opencode tool",
            f"unrendered tool definition: {path}",
        )
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in content:
        return Diagnostic(
            "warn",
            "opencode tool",
            f"registered to another checkout or install: {path}",
        )
    return Diagnostic("ok", "opencode tool", str(path))


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


def _forge_checks(workspace: Path, runner: Runner) -> tuple[Diagnostic, ...]:
    if shutil.which("git") is None:
        return (Diagnostic("fail", "forge", "git not found on PATH"),)
    try:
        remote = infer_forge_remote(workspace, runner=runner)
    except ForgeRemoteError as error:
        return (Diagnostic("warn", "forge", str(error)),)
    cli = "gh" if remote.provider == "github" else "glab"
    if shutil.which(cli) is None:
        return (
            Diagnostic("fail", "forge", f"{remote.provider} remote requires {cli}"),
        )
    detail = f"{remote.provider} via {remote.name}: {remote.repo}"
    diagnostics = [Diagnostic("ok", "forge", detail)]
    if remote.provider == "github":
        diagnostics.extend(_github_readiness_checks(remote.repo, workspace, runner))
    else:
        diagnostics.extend(_gitlab_readiness_checks(remote, workspace, runner))
    return tuple(diagnostics)


def _github_readiness_checks(
    repo: str,
    workspace: Path,
    runner: Runner,
) -> tuple[Diagnostic, ...]:
    auth = runner(["gh", "auth", "status"], workspace)
    repo_view = runner(["gh", "repo", "view", repo], workspace)
    rulesets = runner(["gh", "api", f"repos/{repo}/rulesets"], workspace)
    return (
        _diagnostic_from_result(
            auth,
            name="forge auth",
            ok_detail="gh auth available",
            failure_status="fail",
        ),
        _diagnostic_from_result(
            repo_view,
            name="forge repo",
            ok_detail=f"readable: {repo}",
            failure_status="fail",
        ),
        _diagnostic_from_result(
            rulesets,
            name="forge rulesets",
            ok_detail="readable",
            failure_status="warn",
        ),
    )


def _gitlab_readiness_checks(
    remote: ForgeRemote,
    workspace: Path,
    runner: Runner,
) -> tuple[Diagnostic, ...]:
    repo_selector = _gitlab_repo_selector(remote)
    auth = runner(["glab", "auth", "status", "--hostname", remote.host], workspace)
    repo_view = runner(["glab", "repo", "view", repo_selector], workspace)
    return (
        _diagnostic_from_result(
            auth,
            name="forge auth",
            ok_detail="glab auth available",
            failure_status="fail",
        ),
        _diagnostic_from_result(
            repo_view,
            name="forge repo",
            ok_detail=f"readable: {repo_selector}",
            failure_status="fail",
        ),
    )


def _diagnostic_from_result(
    result: subprocess.CompletedProcess[str],
    *,
    name: str,
    ok_detail: str,
    failure_status: DiagnosticStatus,
) -> Diagnostic:
    if result.returncode == 0:
        return Diagnostic("ok", name, ok_detail)
    return Diagnostic(failure_status, name, _result_message(result))


def _result_message(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or "command failed"


def _gitlab_repo_selector(remote: ForgeRemote) -> str:
    if remote.host == "gitlab.com":
        return remote.repo
    return f"https://{remote.host}/{remote.repo}"


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
    try:
        parse_branch(state.branch)
    except ValueError as error:
        return Diagnostic("fail", "lane state", str(error))
    if (
        state.status in {"review", "finalized", "merged", "cleaned"}
        and state.pr is None
    ):
        return Diagnostic("warn", "lane state", f"{state.id} ({state.status}, no PR)")
    return Diagnostic("ok", "lane state", f"{state.id} ({state.status})")


def _run(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
