from __future__ import annotations

import pytest

from lane.branches import parse_branch


@pytest.mark.parametrize(
    "branch_type",
    [
        "build",
        "chore",
        "ci",
        "docs",
        "fix",
        "hotfix",
        "perf",
        "refactor",
        "revert",
        "style",
        "task",
        "test",
    ],
)
def test_parse_branch_infers_lane_lite_schema(branch_type: str) -> None:
    branch = parse_branch(f"{branch_type}/login-redirect")

    assert branch.branch == f"{branch_type}/login-redirect"
    assert branch.branch_type == branch_type
    assert branch.slug == "login-redirect"
    assert branch.spec_schema == "lane-lite"


def test_parse_branch_infers_spec_driven_schema() -> None:
    branch = parse_branch("feat/review-orchestration")

    assert branch.spec_schema == "spec-driven"


@pytest.mark.parametrize("branch", ["fix", "Fix/login", "unknown/login", "fix/"])
def test_parse_branch_rejects_invalid_branch(branch: str) -> None:
    with pytest.raises(ValueError):
        parse_branch(branch)
