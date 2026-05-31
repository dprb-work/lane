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


def test_run_review_uses_builtin_default_without_reviewer_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")
    calls: list[tuple[list[str], Path]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"agent-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"agentId":"agent-1","status":"idle"}')
        return _result("Verdict: approve\nComments: none")

    result = run_review(tmp_path, runner=runner)

    assert result.review == "approve"
    assert [run.agent for run in result.runs] == ["default"]
    assert calls[0][0][:2] == ["paseo", "run"]
    assert "--mode" not in calls[0][0]
    assert "--detach" in calls[0][0]
    assert "Lane Default Reviewer" in calls[0][0][2]
    assert calls[1][0] == ["paseo", "wait", "agent-1", "--timeout", "1800", "--json"]
    assert calls[2][0] == ["paseo", "logs", "agent-1", "--tail", "200"]
    assert calls[0][1] == tmp_path


def test_run_review_uses_single_configured_reviewer_without_judge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewers = tmp_path / "reviewers"
    reviewers.mkdir()
    (reviewers / "quality.md").write_text("Quality rubric", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"quality-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"agentId":"quality-1","status":"idle"}')
        return _result("Verdict: approve")

    result = run_review(tmp_path, runner=runner, reviewers_dir=reviewers)

    assert result.review == "approve"
    assert [run.agent for run in result.runs] == ["quality"]
    assert calls[0][:2] == ["paseo", "run"]
    assert "Quality rubric" in calls[0][2]
    assert len([call for call in calls if call[:2] == ["paseo", "run"]]) == 1


def test_run_review_routes_known_reviewers_and_runs_judge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewers = tmp_path / "reviewers"
    reviewers.mkdir()
    for name in ("quality", "tests", "llm-smells", "security"):
        (reviewers / f"{name}.md").write_text(f"{name} rubric", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:2] == ["paseo", "run"] and "--detach" in argv:
            name = argv[argv.index("--label") + 1].split("=", 1)[1]
            return _result(f'{{"agentId":"{name}-1","status":"created"}}')
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"judge-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result("{\"status\":\"idle\"}")
        return _result("Verdict: approve")

    result = run_review(
        tmp_path,
        runner=runner,
        reviewers_dir=reviewers,
        changed_paths=("src/lane/review.py", "tests/test_review.py"),
    )

    assert result.review == "approve"
    assert [run.agent for run in result.runs] == [
        "quality",
        "tests",
        "llm-smells",
        "judge",
    ]
    assert calls[0][:2] == ["paseo", "run"]
    assert calls[1][:2] == ["paseo", "run"]
    assert calls[2][:2] == ["paseo", "run"]
    assert "--detach" in calls[0]
    assert calls[9][:2] == ["paseo", "run"]
    assert "--detach" not in calls[9]
    assert "Lane Review Judge" in calls[9][2]


def test_run_review_routes_security_for_sensitive_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewers = tmp_path / "reviewers"
    reviewers.mkdir()
    for name in ("quality", "security"):
        (reviewers / f"{name}.md").write_text(f"{name} rubric", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"] and "--detach" in argv:
            name = argv[argv.index("--label") + 1].split("=", 1)[1]
            return _result(f'{{"agentId":"{name}-1","status":"completed"}}')
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"judge-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"status":"idle"}')
        return _result("Verdict: approve")

    result = run_review(
        tmp_path,
        runner=runner,
        reviewers_dir=reviewers,
        changed_paths=("src/auth/session.py",),
    )

    assert [run.agent for run in result.runs] == ["quality", "security", "judge"]


def test_run_review_falls_back_when_multiple_configured_reviewers_do_not_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewers = tmp_path / "reviewers"
    reviewers.mkdir()
    (reviewers / "security.md").write_text("Security rubric", encoding="utf-8")
    (reviewers / "unknown.md").write_text("Unknown rubric", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            assert "Lane Default Reviewer" in argv[2]
            return _result('{"agentId":"default-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"status":"idle"}')
        return _result("Verdict: approve")

    result = run_review(
        tmp_path,
        runner=runner,
        reviewers_dir=reviewers,
        changed_paths=("README.md",),
    )

    assert result.review == "approve"
    assert [run.agent for run in result.runs] == ["default"]


def test_run_review_uses_explicit_reviewers_from_configured_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewers = tmp_path / "reviewers"
    reviewers.mkdir()
    (reviewers / "quality.md").write_text("Quality rubric", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"quality-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"status":"idle"}')
        return _result("Verdict: comment")

    result = run_review(
        tmp_path,
        runner=runner,
        reviewers_dir=reviewers,
        expected=("quality.md",),
    )

    assert result.review == "comment"
    assert result.missing_agents == ()
    assert [run.agent for run in result.runs] == ["quality"]


def test_run_review_reports_missing_explicit_reviewer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    result = run_review(
        tmp_path,
        runner=lambda argv, cwd: _result(""),
        expected=("quality",),
    )

    assert result.review == "reject"
    assert result.runs == ()
    assert result.missing_agents == ("quality",)


def test_run_review_rejects_when_any_explicit_reviewer_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewers = tmp_path / "reviewers"
    reviewers.mkdir()
    (reviewers / "quality.md").write_text("Quality rubric", encoding="utf-8")
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"quality-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"status":"idle"}')
        return _result("Verdict: approve")

    result = run_review(
        tmp_path,
        runner=runner,
        reviewers_dir=reviewers,
        expected=("quality", "security"),
    )

    assert result.review == "reject"
    assert result.missing_agents == ("security",)
    assert [run.agent for run in result.runs] == ["quality"]


def test_run_review_rejects_when_reviewer_wait_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"reviewer-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result("wait failed", returncode=1)
        return _result("Verdict: approve")

    result = run_review(tmp_path, runner=runner)

    assert result.review == "reject"


def test_run_review_rejects_when_reviewer_wait_times_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"reviewer-1","status":"completed"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"agentId":"reviewer-1","status":"timeout"}')
        return _result("Verdict: approve")

    result = run_review(tmp_path, runner=runner)

    assert result.review == "reject"


def test_run_review_rejects_on_explicit_reject_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"agent-1","status":"created"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"agentId":"agent-1","status":"idle"}')
        return _result("Verdict: reject\nReason: request changes")

    result = run_review(tmp_path, runner=runner)

    assert result.review == "reject"


def test_run_review_does_not_parse_verdict_from_prose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"agent-1","status":"created"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"agentId":"agent-1","status":"idle"}')
        return _result("Verdict: approve\nComments: none; no reject-worthy issues")

    result = run_review(tmp_path, runner=runner)

    assert result.review == "approve"


def test_run_review_treats_missing_verdict_as_comment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["paseo", "run"]:
            return _result('{"agentId":"agent-1","status":"created"}')
        if argv[:2] == ["paseo", "wait"]:
            return _result('{"agentId":"agent-1","status":"idle"}')
        return _result("approve")

    result = run_review(tmp_path, runner=runner)

    assert result.review == "comment"


def test_run_review_missing_paseo_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.review.shutil.which", lambda _: None)

    with pytest.raises(ReviewError, match="paseo CLI not found"):
        run_review(tmp_path, runner=lambda argv, cwd: _result("approve"))


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
