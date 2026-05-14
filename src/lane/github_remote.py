from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lane.forge_remote import (
    ForgeRemoteError,
    infer_forge_remote,
    parse_forge_remote_url,
)


class GitHubRemoteError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubRemote:
    name: str
    repo: str


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def infer_github_remote(cwd: Path, *, runner: Runner) -> GitHubRemote:
    try:
        remote = infer_forge_remote(cwd, runner=runner, provider="github")
    except ForgeRemoteError as error:
        raise GitHubRemoteError(str(error)) from error
    return GitHubRemote(name=remote.name, repo=remote.repo)


def parse_github_remote_url(remote: str) -> str:
    try:
        provider, repo = parse_forge_remote_url(remote)
    except ForgeRemoteError as error:
        raise GitHubRemoteError(str(error)) from error
    if provider != "github":
        raise GitHubRemoteError(f"not a GitHub remote: {remote}")
    return repo
