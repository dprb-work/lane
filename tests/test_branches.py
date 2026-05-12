from __future__ import annotations

import pytest

from lane.branches import parse_branch


def test_parse_branch_infers_lane_lite_schema() -> None:
    branch = parse_branch("fix/login-redirect")

    assert branch.branch == "fix/login-redirect"
    assert branch.branch_type == "fix"
    assert branch.slug == "login-redirect"
    assert branch.spec_schema == "lane-lite"


def test_parse_branch_infers_spec_driven_schema() -> None:
    branch = parse_branch("feat/review-orchestration")

    assert branch.spec_schema == "spec-driven"


@pytest.mark.parametrize("branch", ["fix", "Fix/login", "unknown/login", "fix/"])
def test_parse_branch_rejects_invalid_branch(branch: str) -> None:
    with pytest.raises(ValueError):
        parse_branch(branch)
