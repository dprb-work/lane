from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


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


class Runner(Protocol):
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


def run_verify(workspace: Path, *, runner: Runner | None = None) -> VerifyResult:
    command = discover_verify_command(workspace)
    executable = command.argv[0]
    if shutil.which(executable) is None:
        raise VerifyError(
            f"required verifier executable not found on PATH: {executable}"
        )

    runner = _run if runner is None else runner
    result = runner(command.argv, workspace)
    return VerifyResult(
        command=command,
        exit_status=result.returncode,
        summary=_summarize_output(result.stdout, result.stderr),
    )


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
