from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lane.state import ReviewStatus

EXPECTED_REVIEW_AGENTS = (
    "lane-security-reviewer",
    "lane-quality-reviewer",
    "lane-test-reviewer",
)


class ReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewRun:
    agent: str
    exit_status: int
    output: str


@dataclass(frozen=True)
class ReviewResult:
    review: ReviewStatus
    runs: tuple[ReviewRun, ...]
    missing_agents: tuple[str, ...]


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def available_review_agents(
    *,
    agents_dir: Path | None = None,
    expected: tuple[str, ...] = EXPECTED_REVIEW_AGENTS,
) -> tuple[str, ...]:
    agents_dir = (
        Path.home() / ".config" / "opencode" / "agents"
        if agents_dir is None
        else agents_dir
    )
    return tuple(agent for agent in expected if (agents_dir / f"{agent}.md").exists())


def run_review(
    workspace: Path,
    *,
    runner: Runner | None = None,
    agents_dir: Path | None = None,
    expected: tuple[str, ...] = EXPECTED_REVIEW_AGENTS,
) -> ReviewResult:
    available = available_review_agents(agents_dir=agents_dir, expected=expected)
    missing = tuple(agent for agent in expected if agent not in available)
    if not available:
        return ReviewResult(review="none", runs=(), missing_agents=missing)

    if shutil.which("opencode") is None:
        raise ReviewError("opencode CLI not found on PATH")

    runner = _run if runner is None else runner
    runs = tuple(_run_agent(agent, workspace, runner) for agent in available)
    return ReviewResult(
        review=_aggregate_review(runs),
        runs=runs,
        missing_agents=missing,
    )


def _run_agent(agent: str, workspace: Path, runner: Runner) -> ReviewRun:
    result = runner(
        [
            "opencode",
            "run",
            "Review this lane. Include exactly one verdict line: "
            "Verdict: approve, comment, or reject.",
            "--agent",
            agent,
            "--dir",
            str(workspace),
        ],
        workspace,
    )
    output = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    return ReviewRun(agent=agent, exit_status=result.returncode, output=output)


def _aggregate_review(runs: tuple[ReviewRun, ...]) -> ReviewStatus:
    if not runs:
        return "none"
    if any(run.exit_status != 0 for run in runs):
        return "reject"

    verdicts = [_explicit_verdict(run.output) for run in runs]
    if any(verdict == "reject" for verdict in verdicts):
        return "reject"
    if any(verdict == "comment" for verdict in verdicts):
        return "comment"
    if any(verdict is None for verdict in verdicts):
        return "comment"
    return "approve"


def _explicit_verdict(output: str) -> ReviewStatus | None:
    for line in output.splitlines():
        match = re.fullmatch(
            r"\s*verdict\s*:\s*(approve|comment|reject)\s*",
            line,
            flags=re.IGNORECASE,
        )
        if match is not None:
            return match.group(1).lower()  # type: ignore[return-value]
    return None


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
