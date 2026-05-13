from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class PaseoError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaseoWorktree:
    name: str
    branch: str
    path: Path


@dataclass(frozen=True)
class PaseoArchiveResult:
    name: str
    removed_agents: tuple[str, ...]


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        pass


def create_worktree(
    branch: str,
    *,
    base: str,
    cwd: Path,
    worktree_slug: str | None = None,
    runner: Runner | None = None,
) -> PaseoWorktree:
    raw = _run_json(
        [
            "paseo",
            "worktree",
            "create",
            "--mode",
            "branch-off",
            "--new-branch",
            worktree_slug or branch,
            "--base",
            base,
            "--cwd",
            str(cwd),
            "--json",
        ],
        cwd=cwd,
        runner=_run if runner is None else runner,
    )
    return _worktree_from_create(raw)


def rename_current_branch(
    branch: str,
    *,
    cwd: Path,
    runner: Runner | None = None,
) -> None:
    runner = _run if runner is None else runner
    result = _run_command(["git", "branch", "-m", branch], cwd=cwd, runner=runner)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise PaseoError(f"git branch rename failed: {message}")


def list_worktrees(*, runner: Runner | None = None) -> list[PaseoWorktree]:
    runner = _run if runner is None else runner
    raw = _run_json(["paseo", "worktree", "ls", "--json"], cwd=None, runner=runner)
    if not isinstance(raw, list):
        raise PaseoError("paseo worktree ls returned invalid JSON")
    return [_worktree_from_list_item(item) for item in raw]


def archive_worktree(
    name: str,
    *,
    runner: Runner | None = None,
) -> PaseoArchiveResult:
    runner = _run if runner is None else runner
    raw = _run_json(
        ["paseo", "worktree", "archive", name, "--json"],
        cwd=None,
        runner=runner,
    )
    if not isinstance(raw, dict):
        raise PaseoError("paseo worktree archive returned invalid JSON")
    return PaseoArchiveResult(
        name=_required_str(raw, "name"),
        removed_agents=tuple(_required_str_list(raw, "removedAgents")),
    )


def _run_json(argv: list[str], *, cwd: Path | None, runner: Runner) -> Any:
    result = _run_command(argv, cwd=cwd, runner=runner)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise PaseoError(f"{' '.join(argv[:3])} failed: {message}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise PaseoError("paseo returned invalid JSON") from error


def _run_command(
    argv: list[str],
    *,
    cwd: Path | None,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    if shutil.which(argv[0]) is None:
        raise PaseoError(f"{argv[0]} CLI not found on PATH")
    return runner(argv, cwd)


def _run(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )


def _worktree_from_create(raw: Any) -> PaseoWorktree:
    if not isinstance(raw, dict):
        raise PaseoError("paseo worktree create returned invalid JSON")
    return PaseoWorktree(
        name=_required_str(raw, "name"),
        branch=_required_str(raw, "branchName"),
        path=Path(_required_str(raw, "worktreePath")),
    )


def _worktree_from_list_item(raw: Any) -> PaseoWorktree:
    if not isinstance(raw, dict):
        raise PaseoError("paseo worktree ls returned invalid JSON")
    return PaseoWorktree(
        name=_required_str(raw, "name"),
        branch=_required_str(raw, "branch"),
        path=Path(_required_str(raw, "cwd")).expanduser(),
    )


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or value == "":
        raise PaseoError(f"paseo JSON field {key!r} must be a non-empty string")
    return value


def _required_str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PaseoError(f"paseo JSON field {key!r} must be a string list")
    return value
