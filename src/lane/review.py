from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lane.state import ReviewStatus

EXPECTED_REVIEW_AGENTS = (
    "lane-review-security",
    "lane-review-quality",
    "lane-review-tests",
)
DEFAULT_REVIEW_JUDGE = "lane-review-judge"


class ReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewRun:
    agent: str
    paseo_agent_id: str | None
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


def run_review(
    workspace: Path,
    *,
    runner: Runner | None = None,
    expected: tuple[str, ...] = EXPECTED_REVIEW_AGENTS,
    judge: str = DEFAULT_REVIEW_JUDGE,
) -> ReviewResult:
    agents = tuple(_normalize_agent_name(agent) for agent in expected)
    if not agents:
        return ReviewResult(review="none", runs=(), missing_agents=())

    paseo = _paseo_executable(workspace)
    if paseo is None:
        raise ReviewError("paseo CLI not found on PATH")

    runner = _run if runner is None else runner
    reviewer_runs = _run_reviewers(agents, paseo, workspace, runner)
    judge_run = _run_judge(
        _normalize_agent_name(judge),
        reviewer_runs,
        paseo,
        workspace,
        runner,
    )
    runs = (*reviewer_runs, judge_run)
    return ReviewResult(
        review=_aggregate_review(runs),
        runs=runs,
        missing_agents=(),
    )


def _run_reviewers(
    agents: tuple[str, ...],
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> tuple[ReviewRun, ...]:
    started = tuple(
        _start_reviewer(agent, paseo, workspace, runner) for agent in agents
    )
    return tuple(_collect_reviewer(run, paseo, workspace, runner) for run in started)


def _start_reviewer(
    agent: str,
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> ReviewRun:
    prompt = (
        f"Review this lane using the {agent} review profile. "
        "Use the configured Paseo provider. Include exactly one verdict line: "
        "Verdict: approve, comment, or reject."
    )
    run = runner(
        [
            paseo,
            "run",
            prompt,
            "--title",
            f"lane review: {agent}",
            "--cwd",
            str(workspace),
            "--mode",
            agent,
            "--label",
            f"lane.review={agent}",
            "--detach",
            "--json",
        ],
        workspace,
    )
    agent_id = _agent_id_from_json(run.stdout)
    return ReviewRun(
        agent=agent,
        paseo_agent_id=agent_id,
        exit_status=run.returncode,
        output=_combined_output(run),
    )


def _collect_reviewer(
    run: ReviewRun,
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> ReviewRun:
    if run.paseo_agent_id is None:
        return run
    wait = runner(
        [paseo, "wait", run.paseo_agent_id, "--timeout", "1800", "--json"],
        workspace,
    )
    logs = _logs(run.paseo_agent_id, paseo, workspace, runner)
    return ReviewRun(
        agent=run.agent,
        paseo_agent_id=run.paseo_agent_id,
        exit_status=run.exit_status or wait.returncode or logs.returncode,
        output="\n".join(
            part
            for part in (run.output, _combined_output(wait), _combined_output(logs))
            if part
        ),
    )


def _run_judge(
    judge: str,
    reviewers: tuple[ReviewRun, ...],
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> ReviewRun:
    prompt = (
        "Prioritize and contextualize these lane review findings. "
        "Return the final review result with exactly one verdict line: "
        "Verdict: approve, comment, or reject.\n\n"
        f"Reviewer findings:\n{_reviewer_packet(reviewers)}"
    )
    run = runner(
        [
            paseo,
            "run",
            prompt,
            "--title",
            "lane review: judge",
            "--cwd",
            str(workspace),
            "--mode",
            judge,
            "--label",
            "lane.review=judge",
            "--wait-timeout",
            "30m",
            "--json",
        ],
        workspace,
    )
    agent_id = _agent_id_from_json(run.stdout)
    logs = None
    if agent_id is not None:
        logs = _logs(agent_id, paseo, workspace, runner)
    output = "\n".join(
        part
        for part in (
            _combined_output(run),
            None if logs is None else logs.stdout.strip(),
            None if logs is None else logs.stderr.strip(),
        )
        if part
    )
    exit_status = run.returncode if logs is None else run.returncode or logs.returncode
    return ReviewRun(
        agent=judge,
        paseo_agent_id=agent_id,
        exit_status=exit_status,
        output=output,
    )


def _logs(
    agent_id: str,
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    return runner(
        [paseo, "logs", agent_id, "--tail", "200"],
        workspace,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )


def _reviewer_packet(reviewers: tuple[ReviewRun, ...]) -> str:
    return "\n\n".join(
        f"## {run.agent}\n"
        f"Paseo agent: {run.paseo_agent_id or 'unknown'}\n"
        f"Exit status: {run.exit_status}\n"
        f"Output:\n{run.output}"
        for run in reviewers
    )


def _normalize_agent_name(agent: str) -> str:
    stripped = agent.strip()
    if stripped.endswith(".md"):
        return stripped[:-3]
    return stripped


def _agent_id_from_json(output: str) -> str | None:
    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    agent_id = raw.get("agentId")
    if isinstance(agent_id, str) and agent_id:
        return agent_id
    return None


def _paseo_executable(workspace: Path) -> str | None:
    path = workspace / "node_modules" / ".bin" / "paseo"
    if path.exists():
        return str(path)
    if shutil.which("paseo") is not None:
        return "paseo"
    return None


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
