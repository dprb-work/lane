from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.review import ReviewError, run_review


def test_run_review_reports_none_for_empty_agent_list(tmp_path: Path) -> None:
    result = run_review(tmp_path, expected=())

    assert result.review == "none"
    assert result.runs == ()
    assert result.missing_agents == ()


def test_run_review_invokes_available_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")
    calls: list[tuple[list[str], Path]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        if argv[:2] == ["paseo", "run"] and "--detach" in argv:
            return _result('{"agentId":"agent-1","status":"completed"}')
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"judge-1","status":"completed"}')
        return _result("Verdict: approve\nComments: none")

    result = run_review(tmp_path, runner=runner, expected=("lane-review-quality.md",))

    assert result.review == "approve"
    assert result.runs[0].agent == "lane-review-quality"
    assert result.runs[0].paseo_agent_id == "agent-1"
    assert result.runs[1].agent == "lane-review-judge"
    assert result.runs[1].paseo_agent_id == "judge-1"
    assert calls[0][0][:2] == ["paseo", "run"]
    assert "--detach" in calls[0][0]
    assert "--mode" in calls[0][0]
    assert "lane-review-quality" in calls[0][0]
    assert calls[1][0] == ["paseo", "wait", "agent-1", "--timeout", "1800", "--json"]
    assert calls[2][0] == ["paseo", "logs", "agent-1", "--tail", "200"]
    assert calls[3][0][:2] == ["paseo", "run"]
    assert "--detach" not in calls[3][0]
    assert "lane-review-judge" in calls[3][0]
    assert calls[0][1] == tmp_path


def test_run_review_starts_reviewers_before_waiting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:2] == ["paseo", "run"] and "--detach" in argv:
            agent_id = "agent-1" if "lane-review-a" in argv else "agent-2"
            return _result(f'{{"agentId":"{agent_id}","status":"created"}}')
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"judge-1","status":"completed"}')
        return _result("Verdict: approve")

    run_review(
        tmp_path,
        runner=runner,
        expected=("lane-review-a", "lane-review-b"),
    )

    assert calls[0][:2] == ["paseo", "run"]
    assert calls[1][:2] == ["paseo", "run"]
    assert "--detach" in calls[0]
    assert "--detach" in calls[1]
    assert calls[2][:2] == ["paseo", "wait"]


def test_run_review_rejects_when_reviewer_wait_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            agent_id = "reviewer-1" if "--detach" in argv else "judge-1"
            return _result(f'{{"agentId":"{agent_id}","status":"completed"}}')
        if argv[:2] == ["paseo", "wait"]:
            return _result("wait failed", returncode=1)
        return _result("Verdict: approve")

    result = run_review(
        tmp_path,
        runner=runner,
        expected=("lane-review-quality",),
    )

    assert result.review == "reject"


def test_run_review_uses_judge_verdict_over_reviewer_verdicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            agent_id = "reviewer-1" if "--detach" in argv else "judge-1"
            return _result(f'{{"agentId":"{agent_id}","status":"completed"}}')
        if argv[:2] == ["paseo", "logs"] and argv[2] == "reviewer-1":
            return _result("Verdict: reject\nFalse positive")
        return _result("Verdict: approve")

    result = run_review(
        tmp_path,
        runner=runner,
        expected=("lane-review-quality",),
    )

    assert result.review == "approve"


def test_run_review_rejects_on_explicit_reject_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result(
            '{"agentId":"agent-1","status":"created"}'
            if argv[:2] == ["paseo", "run"]
            else "Verdict: reject\nReason: request changes"
        ),
        expected=("lane-review-quality",),
    )

    assert result.review == "reject"


def test_run_review_does_not_parse_verdict_from_prose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result(
            '{"agentId":"agent-1","status":"created"}'
            if argv[:2] == ["paseo", "run"]
            else "Verdict: approve\nComments: none; no reject-worthy issues"
        ),
        expected=("lane-review-quality",),
    )

    assert result.review == "approve"


def test_run_review_treats_missing_verdict_as_comment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result(
            '{"agentId":"agent-1","status":"created"}'
            if argv[:2] == ["paseo", "run"]
            else "approve"
        ),
        expected=("lane-review-quality",),
    )

    assert result.review == "comment"


def test_run_review_missing_paseo_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: None)

    with pytest.raises(ReviewError, match="paseo CLI not found"):
        run_review(
            tmp_path,
            runner=lambda argv, cwd: _result("approve"),
            expected=("lane-review-quality",),
        )


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["paseo"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
