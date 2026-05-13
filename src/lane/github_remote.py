from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


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
    result = runner(["git", "remote", "-v"], cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "remotes not found"
        raise GitHubRemoteError(f"failed to infer GitHub remote: {message}")

    for line in result.stdout.splitlines():
        remote = _remote_from_verbose_line(line)
        if remote is not None:
            return remote

    raise GitHubRemoteError("no GitHub remote found")


def parse_github_remote_url(remote: str) -> str:
    ssh_match = re.fullmatch(
        r"git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?",
        remote,
    )
    if ssh_match is not None:
        return ssh_match.group("repo")

    parsed = urlparse(remote)
    if parsed.hostname != "github.com":
        raise GitHubRemoteError(f"not a GitHub remote: {remote}")
    repo = parsed.path.strip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if repo.count("/") != 1:
        raise GitHubRemoteError(f"cannot parse GitHub repo from remote: {remote}")
    return repo


def _remote_from_verbose_line(line: str) -> GitHubRemote | None:
    parts = line.split()
    if len(parts) < 3 or parts[2] != "(fetch)":
        return None
    try:
        repo = parse_github_remote_url(parts[1])
    except GitHubRemoteError:
        return None
    return GitHubRemote(name=parts[0], repo=repo)
