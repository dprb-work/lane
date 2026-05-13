from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.review import ReviewError, available_review_agents, run_review


def test_available_review_agents_uses_expected_agent_files(tmp_path: Path) -> None:
    (tmp_path / "lane-quality-reviewer.md").write_text("review", encoding="utf-8")

    assert available_review_agents(agents_dir=tmp_path) == ("lane-quality-reviewer",)


def test_run_review_reports_missing_agents_without_invocation(tmp_path: Path) -> None:
    result = run_review(tmp_path, agents_dir=tmp_path)

    assert result.review == "none"
    assert result.runs == ()
    assert result.missing_agents == (
        "lane-security-reviewer",
        "lane-quality-reviewer",
        "lane-test-reviewer",
    )


def test_run_review_invokes_available_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "lane-quality-reviewer.md").write_text("review", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/opencode")
    calls: list[tuple[list[str], Path]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        return _result("Verdict: approve\nComments: none")

    result = run_review(tmp_path, runner=runner, agents_dir=agents)

    assert result.review == "approve"
    assert result.runs[0].agent == "lane-quality-reviewer"
    assert calls[0][0][:2] == ["opencode", "run"]
    assert "lane-quality-reviewer" in calls[0][0]
    assert calls[0][1] == tmp_path


def test_run_review_rejects_on_explicit_reject_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "lane-quality-reviewer.md").write_text("review", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/opencode")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result("Verdict: reject\nReason: request changes"),
        agents_dir=agents,
    )

    assert result.review == "reject"


def test_run_review_does_not_parse_verdict_from_prose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "lane-quality-reviewer.md").write_text("review", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/opencode")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result(
            "Verdict: approve\nComments: none; no reject-worthy issues"
        ),
        agents_dir=agents,
    )

    assert result.review == "approve"


def test_run_review_treats_missing_verdict_as_comment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "lane-quality-reviewer.md").write_text("review", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/opencode")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result("approve"),
        agents_dir=agents,
    )

    assert result.review == "comment"


def test_run_review_missing_opencode_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "lane-quality-reviewer.md").write_text("review", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: None)

    with pytest.raises(ReviewError, match="opencode CLI not found"):
        run_review(
            tmp_path,
            runner=lambda argv, cwd: _result("approve"),
            agents_dir=agents,
        )


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["opencode"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
