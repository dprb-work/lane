from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlparse

ForgeProvider = Literal["github", "gitlab"]


class ForgeRemoteError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForgeRemote:
    provider: ForgeProvider
    name: str
    repo: str


@dataclass(frozen=True)
class GitLabMergeRequest:
    repo_selector: str
    iid: str


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def infer_forge_remote(
    cwd: Path,
    *,
    runner: Runner,
    provider: ForgeProvider | None = None,
) -> ForgeRemote:
    result = runner(["git", "remote", "-v"], cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "remotes not found"
        raise ForgeRemoteError(f"failed to infer forge remote: {message}")

    for line in result.stdout.splitlines():
        remote = _remote_from_verbose_line(line)
        if remote is not None and (provider is None or remote.provider == provider):
            return remote

    if provider is not None:
        raise ForgeRemoteError(f"no {_provider_label(provider)} remote found")
    raise ForgeRemoteError("no GitHub or GitLab remote found")


def parse_forge_remote_url(remote: str) -> tuple[ForgeProvider, str]:
    ssh_match = re.fullmatch(
        r"git@(?P<host>[^:]+):(?P<repo>.+?)(?:\.git)?",
        remote,
    )
    if ssh_match is not None:
        host = ssh_match.group("host")
        repo = _normalize_repo(ssh_match.group("repo"), remote)
        return (_provider_from_host(host), repo)

    parsed = urlparse(remote)
    if parsed.hostname is None:
        raise ForgeRemoteError(f"not a supported forge remote: {remote}")
    repo = _normalize_repo(parsed.path.strip("/"), remote)
    return (_provider_from_host(parsed.hostname), repo)


def provider_from_pr_url(pr_url: str) -> ForgeProvider:
    parsed = urlparse(pr_url)
    if parsed.hostname == "github.com" and "/pull/" in parsed.path:
        return "github"
    if parsed.hostname is not None and "/-/merge_requests/" in parsed.path:
        return "gitlab"
    raise ForgeRemoteError(f"unsupported PR/MR URL: {pr_url}")


def parse_gitlab_mr_url(mr_url: str) -> GitLabMergeRequest:
    parsed = urlparse(mr_url)
    if parsed.hostname is None:
        raise ForgeRemoteError(f"not a GitLab MR URL: {mr_url}")
    marker = "/-/merge_requests/"
    if marker not in parsed.path:
        raise ForgeRemoteError(f"not a GitLab MR URL: {mr_url}")
    repo, iid = parsed.path.strip("/").split(marker.strip("/"), maxsplit=1)
    repo = repo.strip("/")
    iid = iid.strip("/")
    if not repo or not iid:
        raise ForgeRemoteError(f"cannot parse GitLab MR URL: {mr_url}")
    authority = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    return GitLabMergeRequest(
        repo_selector=f"{parsed.scheme}://{authority}/{repo}",
        iid=iid,
    )


def _provider_from_host(host: str) -> ForgeProvider:
    if host == "github.com":
        return "github"
    return "gitlab"


def _provider_label(provider: ForgeProvider) -> str:
    return "GitHub" if provider == "github" else "GitLab"


def _normalize_repo(repo: str, remote: str) -> str:
    if repo.endswith(".git"):
        repo = repo[:-4]
    if repo.count("/") < 1:
        raise ForgeRemoteError(f"cannot parse repo from remote: {remote}")
    return repo


def _remote_from_verbose_line(line: str) -> ForgeRemote | None:
    parts = line.split()
    if len(parts) < 3 or parts[2] != "(fetch)":
        return None
    try:
        provider, repo = parse_forge_remote_url(parts[1])
    except ForgeRemoteError:
        return None
    return ForgeRemote(provider=provider, name=parts[0], repo=repo)
