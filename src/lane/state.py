from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

STATE_SCHEMA = 1
STATE_DIR = ".lane"
STATE_FILE = "state.yaml"

LaneStatus = Literal["active", "review", "finalized", "merged", "aborted", "cleaned"]
ReviewStatus = Literal["none", "approve", "comment", "reject"]

LANE_STATUSES = {"active", "review", "finalized", "merged", "aborted", "cleaned"}
REVIEW_STATUSES = {"none", "approve", "comment", "reject"}


@dataclass(frozen=True)
class VerificationState:
    command: str
    exit_status: int
    head: str
    verified_at: str


@dataclass(frozen=True)
class LaneState:
    schema: int
    id: str
    status: LaneStatus
    branch: str
    base: str
    path: Path
    spec: str
    review: ReviewStatus
    pr: str | None
    verification: VerificationState | None = None


def state_path(workspace: Path) -> Path:
    return workspace / STATE_DIR / STATE_FILE


def state_to_dict(state: LaneState) -> dict[str, object]:
    raw: dict[str, object] = {
        "schema": state.schema,
        "id": state.id,
        "status": state.status,
        "branch": state.branch,
        "base": state.base,
        "path": str(state.path),
        "spec": state.spec,
        "review": state.review,
        "pr": state.pr,
    }
    if state.verification is not None:
        raw["verification"] = {
            "command": state.verification.command,
            "exit_status": state.verification.exit_status,
            "head": state.verification.head,
            "verified_at": state.verification.verified_at,
        }
    return raw


def validate_state(raw: Any) -> LaneState:
    if not isinstance(raw, dict):
        raise ValueError("lane state must be a mapping")

    schema = _required_int(raw, "schema")
    if schema != STATE_SCHEMA:
        raise ValueError(f"unsupported lane state schema {schema!r}")

    status = _required_str(raw, "status")
    if status not in LANE_STATUSES:
        raise ValueError(f"invalid lane status {status!r}")

    review = _required_str(raw, "review")
    if review not in REVIEW_STATUSES:
        raise ValueError(f"invalid review status {review!r}")

    pr = raw.get("pr")
    if pr is not None and not isinstance(pr, str):
        raise ValueError("pr must be a string or null")

    verification = _optional_verification(raw.get("verification"))

    return LaneState(
        schema=schema,
        id=_required_str(raw, "id"),
        status=status,  # type: ignore[arg-type]
        branch=_required_str(raw, "branch"),
        base=_required_str(raw, "base"),
        path=Path(_required_str(raw, "path")),
        spec=_required_str(raw, "spec"),
        review=review,  # type: ignore[arg-type]
        pr=pr,
        verification=verification,
    )


def read_state(workspace: Path) -> LaneState:
    path = state_path(workspace)
    with path.open("r", encoding="utf-8") as handle:
        return validate_state(yaml.safe_load(handle))


def write_state(workspace: Path, state: LaneState) -> Path:
    path = state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(state_to_dict(state), handle, sort_keys=False)
    return path


def find_state_path(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        path = state_path(candidate)
        if path.exists():
            return path
    return None


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_verification(raw: Any) -> VerificationState | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("verification must be a mapping")
    exit_status = _required_int(raw, "exit_status")
    if exit_status < 0:
        raise ValueError("verification exit_status must be non-negative")
    return VerificationState(
        command=_required_str(raw, "command"),
        exit_status=exit_status,
        head=_required_str(raw, "head"),
        verified_at=_required_str(raw, "verified_at"),
    )
