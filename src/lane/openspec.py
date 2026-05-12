from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol


class OpenSpecError(RuntimeError):
    pass


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        pass


def create_spec(
    name: str,
    *,
    schema: str,
    description: str,
    cwd: Path,
    runner: Runner | None = None,
) -> None:
    if shutil.which("openspec") is None:
        raise OpenSpecError("openspec CLI not found on PATH")

    runner = _run if runner is None else runner
    result = runner(
        [
            "openspec",
            "new",
            "change",
            name,
            "--schema",
            schema,
            "--description",
            description,
        ],
        cwd,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise OpenSpecError(f"openspec new change failed: {message}")


def active_spec_path(workspace: Path, spec: str) -> Path:
    return workspace / "openspec" / "changes" / spec


def is_spec_active(workspace: Path, spec: str) -> bool:
    return active_spec_path(workspace, spec).exists()


def require_spec_archived(workspace: Path, spec: str) -> None:
    if is_spec_active(workspace, spec):
        raise OpenSpecError(
            f"spec {spec!r} is still active; archive/sync it before continuing"
        )


def _run(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
