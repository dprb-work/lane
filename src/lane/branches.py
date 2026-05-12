from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED_BRANCH_TYPES = {
    "feat": "spec-driven",
    "fix": "lane-lite",
    "docs": "lane-lite",
    "chore": "lane-lite",
    "test": "lane-lite",
}

_BRANCH_RE = re.compile(
    r"^(?P<branch_type>[a-z][a-z0-9-]*)/(?P<slug>[a-z0-9][a-z0-9._-]*)$"
)


@dataclass(frozen=True)
class BranchInfo:
    branch: str
    branch_type: str
    slug: str
    spec_schema: str


def parse_branch(branch: str) -> BranchInfo:
    match = _BRANCH_RE.fullmatch(branch)
    if match is None:
        raise ValueError(
            "branch must use <type>/<slug>, for example fix/login-redirect"
        )

    branch_type = match.group("branch_type")
    spec_schema = SUPPORTED_BRANCH_TYPES.get(branch_type)
    if spec_schema is None:
        supported = ", ".join(sorted(SUPPORTED_BRANCH_TYPES))
        raise ValueError(
            f"unsupported branch type {branch_type!r}; supported types: {supported}"
        )

    return BranchInfo(
        branch=branch,
        branch_type=branch_type,
        slug=match.group("slug"),
        spec_schema=spec_schema,
    )
