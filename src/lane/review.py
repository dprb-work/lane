from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from lane.state import ReviewStatus

REVIEWERS_DIR_ENV = "LANE_REVIEWERS_DIR"
BUILTIN_REVIEWER = "default"
BUILTIN_JUDGE = "judge"
KNOWN_REVIEWERS = frozenset(("quality", "tests", "llm-smells", "security"))
CODE_EXTENSIONS = frozenset(
    (
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".css",
        ".go",
        ".h",
        ".hpp",
        ".html",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".lua",
        ".php",
        ".py",
        ".rs",
        ".sh",
        ".sql",
        ".swift",
        ".ts",
        ".tsx",
        ".vue",
    )
)
TEST_PATH_RE = re.compile(r"(^|/)(tests?|specs?)(/|$)|(^|/)test_|_test\.")
SECURITY_PATH_RE = re.compile(
    r"auth|permission|secret|token|credential|crypto|tls|ssl|webhook|"
    r"sandbox|policy|role|tenant|session|cookie",
    flags=re.IGNORECASE,
)
SECURITY_EXTENSIONS = frozenset((".pem", ".key", ".crt"))
DEFAULT_REVIEW_AGENTS = (BUILTIN_REVIEWER,)


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


@dataclass(frozen=True)
class ReviewPrompt:
    name: str
    prompt: str
    source: Path | None = None


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
    expected: tuple[str, ...] | None = None,
    judge: str = BUILTIN_JUDGE,
    reviewers_dir: Path | None = None,
    base: str | None = None,
    changed_paths: tuple[str, ...] | None = None,
) -> ReviewResult:
    prompts, missing_agents = _select_review_prompts(
        workspace,
        expected=expected,
        reviewers_dir=reviewers_dir,
        base=base,
        changed_paths=changed_paths,
    )
    if not prompts:
        return ReviewResult(review="none", runs=(), missing_agents=missing_agents)

    paseo = _paseo_executable(workspace)
    if paseo is None:
        raise ReviewError("paseo CLI not found on PATH")

    runner = _run if runner is None else runner
    reviewer_runs = _run_reviewers(prompts, paseo, workspace, runner)
    if len(reviewer_runs) > 1:
        judge_run = _run_judge(
            _judge_prompt(judge),
            reviewer_runs,
            paseo,
            workspace,
            runner,
        )
        runs = (*reviewer_runs, judge_run)
        review = _final_review(reviewer_runs, judge_run)
    else:
        runs = reviewer_runs
        review = _aggregate_review(reviewer_runs)
    return ReviewResult(
        review=review,
        runs=runs,
        missing_agents=missing_agents,
    )


def _select_review_prompts(
    workspace: Path,
    *,
    expected: tuple[str, ...] | None,
    reviewers_dir: Path | None,
    base: str | None,
    changed_paths: tuple[str, ...] | None,
) -> tuple[tuple[ReviewPrompt, ...], tuple[str, ...]]:
    if expected is not None:
        return _select_explicit_prompts(expected, reviewers_dir)

    configured = _load_reviewers(_reviewers_dir(reviewers_dir))
    if len(configured) == 1:
        return tuple(configured.values()), ()
    if len(configured) > 1:
        paths = changed_paths or _changed_paths(workspace, base)
        selected = _route_reviewers(configured, paths)
        if selected:
            return selected, ()
    return (
        ReviewPrompt(BUILTIN_REVIEWER, _asset_text("assets/review/default.md")),
    ), ()


def _select_explicit_prompts(
    expected: tuple[str, ...],
    reviewers_dir: Path | None,
) -> tuple[tuple[ReviewPrompt, ...], tuple[str, ...]]:
    names = tuple(_normalize_agent_name(agent) for agent in expected)
    if not names:
        return (), ()

    configured = _load_reviewers(_reviewers_dir(reviewers_dir))
    prompts: list[ReviewPrompt] = []
    missing: list[str] = []
    for name in names:
        if name == BUILTIN_REVIEWER:
            prompts.append(
                ReviewPrompt(
                    BUILTIN_REVIEWER,
                    _asset_text("assets/review/default.md"),
                )
            )
            continue
        prompt = configured.get(name)
        if prompt is None:
            missing.append(name)
            continue
        prompts.append(prompt)
    return tuple(prompts), tuple(missing)


def _reviewers_dir(path: Path | None) -> Path | None:
    if path is not None:
        return path.expanduser()
    raw = os.environ.get(REVIEWERS_DIR_ENV)
    if raw is None or not raw.strip():
        return None
    return Path(raw).expanduser()


def _load_reviewers(path: Path | None) -> dict[str, ReviewPrompt]:
    if path is None or not path.is_dir():
        return {}
    prompts: dict[str, ReviewPrompt] = {}
    for file in sorted(path.iterdir(), key=lambda item: item.name):
        if not file.is_file() or file.suffix.lower() not in {".md", ".txt"}:
            continue
        name = _normalize_agent_name(file.name)
        text = file.read_text(encoding="utf-8").strip()
        if text:
            prompts[name] = ReviewPrompt(name=name, prompt=text, source=file)
    return prompts


def _route_reviewers(
    configured: dict[str, ReviewPrompt],
    changed_paths: tuple[str, ...],
) -> tuple[ReviewPrompt, ...]:
    selected: list[str] = []
    code_changed = _has_code_change(changed_paths)
    if code_changed and "quality" in configured:
        selected.append("quality")
    if _needs_tests_review(changed_paths, code_changed) and "tests" in configured:
        selected.append("tests")
    if (
        _needs_llm_smells_review(changed_paths, code_changed)
        and "llm-smells" in configured
    ):
        selected.append("llm-smells")
    if _needs_security_review(changed_paths) and "security" in configured:
        selected.append("security")
    return tuple(configured[name] for name in selected)


def _changed_paths(workspace: Path, base: str | None) -> tuple[str, ...]:
    candidates = []
    if base:
        candidates.append(["git", "diff", "--name-only", f"{base}...HEAD"])
        candidates.append(["git", "diff", "--name-only", f"origin/{base}...HEAD"])
    candidates.extend(
        (
            ["git", "diff", "--name-only", "HEAD~1..HEAD"],
            ["git", "diff", "--name-only", "--cached"],
            ["git", "diff", "--name-only"],
        )
    )
    for argv in candidates:
        result = subprocess.run(
            argv,
            cwd=workspace,
            check=False,
            text=True,
            capture_output=True,
        )
        paths = tuple(
            line.strip() for line in result.stdout.splitlines() if line.strip()
        )
        if result.returncode == 0 and paths:
            return paths
    return ()


def _has_code_change(paths: tuple[str, ...]) -> bool:
    return any(Path(path).suffix.lower() in CODE_EXTENSIONS for path in paths)


def _needs_tests_review(paths: tuple[str, ...], code_changed: bool) -> bool:
    return code_changed or any(TEST_PATH_RE.search(path) for path in paths)


def _needs_llm_smells_review(paths: tuple[str, ...], code_changed: bool) -> bool:
    return code_changed or any(
        "agent" in path.lower() or "llm" in path.lower() for path in paths
    )


def _needs_security_review(paths: tuple[str, ...]) -> bool:
    return any(
        SECURITY_PATH_RE.search(path)
        or Path(path).suffix.lower() in SECURITY_EXTENSIONS
        for path in paths
    )


def _run_reviewers(
    prompts: tuple[ReviewPrompt, ...],
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> tuple[ReviewRun, ...]:
    started = tuple(
        _start_reviewer(prompt, paseo, workspace, runner) for prompt in prompts
    )
    return tuple(_collect_reviewer(run, paseo, workspace, runner) for run in started)


def _start_reviewer(
    review_prompt: ReviewPrompt,
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> ReviewRun:
    prompt = (
        f"{review_prompt.prompt}\n\n"
        "Review this lane using the instructions above. "
        "Use the configured Paseo provider. Include exactly one verdict line: "
        "Verdict: approve, comment, or reject."
    )
    run = runner(
        [
            paseo,
            "run",
            prompt,
            "--title",
            f"lane review: {review_prompt.name}",
            "--cwd",
            str(workspace),
            "--label",
            f"lane.review={review_prompt.name}",
            "--detach",
            "--json",
        ],
        workspace,
    )
    agent_id = _agent_id_from_json(run.stdout)
    status_failure = _json_status_exit(run, allowed=("created", "running", "completed"))
    return ReviewRun(
        agent=review_prompt.name,
        paseo_agent_id=agent_id,
        exit_status=run.returncode or status_failure or (0 if agent_id else 1),
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
    status_failure = _json_status_exit(wait, allowed=("idle", "completed"))
    return ReviewRun(
        agent=run.agent,
        paseo_agent_id=run.paseo_agent_id,
        exit_status=(
            run.exit_status or wait.returncode or status_failure or logs.returncode
        ),
        output="\n".join(
            part
            for part in (run.output, _combined_output(wait), _combined_output(logs))
            if part
        ),
    )


def _run_judge(
    judge_prompt: ReviewPrompt,
    reviewers: tuple[ReviewRun, ...],
    paseo: str,
    workspace: Path,
    runner: Runner,
) -> ReviewRun:
    prompt = (
        f"{judge_prompt.prompt}\n\n"
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
            "--label",
            "lane.review=judge",
            "--wait-timeout",
            "30m",
            "--json",
        ],
        workspace,
    )
    agent_id = _agent_id_from_json(run.stdout)
    status_failure = _json_status_exit(run, allowed=("completed", "idle"))
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
    exit_status = run.returncode or status_failure or (0 if agent_id else 1)
    if logs is not None:
        exit_status = exit_status or logs.returncode
    return ReviewRun(
        agent=judge_prompt.name,
        paseo_agent_id=agent_id,
        exit_status=exit_status,
        output=output,
    )


def _judge_prompt(judge: str) -> ReviewPrompt:
    name = _normalize_agent_name(judge)
    if name != BUILTIN_JUDGE:
        return ReviewPrompt(name=name, prompt=_asset_text("assets/review/judge.md"))
    return ReviewPrompt(
        name=BUILTIN_JUDGE,
        prompt=_asset_text("assets/review/judge.md"),
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
    suffix = Path(stripped).suffix.lower()
    if suffix in {".md", ".txt"}:
        return Path(stripped).stem
    return Path(stripped).name


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


def _json_status_exit(
    result: subprocess.CompletedProcess[str],
    *,
    allowed: tuple[str, ...],
) -> int:
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return 1
    if not isinstance(raw, dict):
        return 1
    status = raw.get("status")
    if not isinstance(status, str):
        return 1
    return 0 if status in allowed else 1


def _paseo_executable(workspace: Path) -> str | None:
    path = workspace / "node_modules" / ".bin" / "paseo"
    if path.exists():
        return str(path)
    if shutil.which("paseo") is not None:
        return "paseo"
    return None


def _final_review(
    reviewers: tuple[ReviewRun, ...],
    judge: ReviewRun,
) -> ReviewStatus:
    if any(run.exit_status != 0 for run in (*reviewers, judge)):
        return "reject"
    return _aggregate_review((judge,))


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


def _asset_text(path: str) -> str:
    return files("lane").joinpath(path).read_text(encoding="utf-8").strip()
