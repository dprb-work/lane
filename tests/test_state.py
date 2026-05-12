from __future__ import annotations

from pathlib import Path

import pytest

from lane.state import (
    LaneState,
    find_state_path,
    read_state,
    validate_state,
    write_state,
)


def test_write_and_read_state(tmp_path: Path) -> None:
    state = LaneState(
        schema=1,
        id="login-redirect",
        status="active",
        branch="fix/login-redirect",
        base="main",
        path=tmp_path,
        spec="login-redirect",
        review="none",
        pr=None,
    )

    written = write_state(tmp_path, state)

    assert written == tmp_path / ".lane" / "state.yaml"
    assert read_state(tmp_path) == state


def test_find_state_path_walks_up_from_child(tmp_path: Path) -> None:
    state = LaneState(
        schema=1,
        id="docs-readme",
        status="active",
        branch="docs/readme",
        base="main",
        path=tmp_path,
        spec="docs-readme",
        review="none",
        pr=None,
    )
    write_state(tmp_path, state)
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)

    assert find_state_path(child) == tmp_path / ".lane" / "state.yaml"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", 2),
        ("status", "unknown"),
        ("review", "pending"),
        ("pr", 123),
    ],
)
def test_validate_state_rejects_invalid_values(field: str, value: object) -> None:
    raw: dict[str, object] = {
        "schema": 1,
        "id": "login-redirect",
        "status": "active",
        "branch": "fix/login-redirect",
        "base": "main",
        "path": "/tmp/workspace",
        "spec": "login-redirect",
        "review": "none",
        "pr": None,
    }
    raw[field] = value

    with pytest.raises(ValueError):
        validate_state(raw)
