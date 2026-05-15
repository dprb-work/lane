from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from lane.run import Runner as CommandRunner
from lane.run import run_lane_command
from lane.state import VerificationState


class VerifyError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifyCommand:
    argv: list[str]
    label: str


@dataclass(frozen=True)
class VerifyResult:
    command: VerifyCommand
    exit_status: int
    summary: str


class GitRunner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def discover_verify_command(workspace: Path) -> VerifyCommand:
    if _justfile_has_verify(workspace):
        return VerifyCommand(argv=["just", "verify"], label="just verify")

    package_json = workspace / "package.json"
    if package_json.exists() and _package_has_verify(package_json):
        return VerifyCommand(argv=["npm", "run", "verify"], label="npm run verify")

    raise VerifyError("no verify command found; add `just verify` or `npm run verify`")


def run_verify(
    workspace: Path,
    *,
    runner: CommandRunner | None = None,
) -> VerifyResult:
    command = discover_verify_command(workspace)
    executable = command.argv[0]
    if shutil.which(executable) is None:
        raise VerifyError(
            f"required verifier executable not found on PATH: {executable}"
        )

    result = run_lane_command(
        workspace,
        command.argv,
        capture_output=True,
        runner=runner,
    )
    return VerifyResult(
        command=command,
        exit_status=result.exit_status,
        summary=_summarize_output(result.stdout, result.stderr),
    )


def current_head(workspace: Path, *, runner: GitRunner | None = None) -> str:
    runner = _run if runner is None else runner
    result = runner(["git", "rev-parse", "HEAD"], workspace)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise VerifyError(f"git rev-parse HEAD failed: {message}")
    head = result.stdout.strip()
    if head == "":
        raise VerifyError("git rev-parse HEAD returned no commit")
    return head


def verification_state(result: VerifyResult, head: str) -> VerificationState:
    return VerificationState(
        command=result.command.label,
        exit_status=result.exit_status,
        head=head,
        verified_at=datetime.now(UTC).isoformat(),
    )


def verify_result_from_state(state: VerificationState) -> VerifyResult:
    return VerifyResult(
        command=VerifyCommand(argv=[], label=state.command),
        exit_status=state.exit_status,
        summary=f"fresh verification recorded at {state.verified_at}",
    )


def require_fresh_verification(
    verification: VerificationState | None,
    head: str,
) -> VerificationState:
    if verification is None:
        raise VerifyError(
            "no fresh verification recorded; run `lane verify` or omit `--no-verify`"
        )
    if verification.exit_status != 0:
        raise VerifyError("last verification did not succeed; run `lane verify`")
    if verification.head != head:
        raise VerifyError(
            "last verification does not apply to current HEAD; run `lane verify`"
        )
    return verification


def _justfile_has_verify(workspace: Path) -> bool:
    justfile = next(
        (
            workspace / name
            for name in ("justfile", "Justfile")
            if (workspace / name).exists()
        ),
        None,
    )
    if justfile is None:
        return False

    for line in justfile.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("verify:") or stripped == "verify":
            return True
    return False


def _package_has_verify(package_json: Path) -> bool:
    try:
        raw = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise VerifyError(f"invalid package.json: {error}") from error

    scripts = raw.get("scripts")
    return isinstance(scripts, dict) and isinstance(scripts.get("verify"), str)


def _summarize_output(stdout: str, stderr: str) -> str:
    combined = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if combined == "":
        return "no output"
    lines = combined.splitlines()
    return "\n".join(lines[-20:])


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
