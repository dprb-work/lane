from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

LANE_IGNORE_ENTRY = ".lane/"
LANE_LITE_SCHEMA = "lane-lite"


@dataclass(frozen=True)
class InitResult:
    gitignore: Path
    schema_dir: Path
    missing_tools: tuple[str, ...]


def run_init(target: Path, *, home: Path | None = None) -> InitResult:
    target = target.resolve()
    ensure_lane_ignored(target)
    schema_dir = install_lane_lite_schema(Path.home() if home is None else home)
    missing_tools = tuple(
        tool for tool in ("paseo", "openspec") if shutil.which(tool) is None
    )
    return InitResult(
        gitignore=target / ".gitignore",
        schema_dir=schema_dir,
        missing_tools=missing_tools,
    )


def ensure_lane_ignored(target: Path) -> None:
    gitignore = target / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    entries = existing.splitlines()
    if LANE_IGNORE_ENTRY in entries:
        return

    prefix = "" if existing == "" or existing.endswith("\n") else "\n"
    gitignore.write_text(
        f"{existing}{prefix}{LANE_IGNORE_ENTRY}\n",
        encoding="utf-8",
    )


def install_lane_lite_schema(home: Path) -> Path:
    schema_dir = home / ".local" / "share" / "openspec" / "schemas" / LANE_LITE_SCHEMA
    template_dir = schema_dir / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)

    schema_file = schema_dir / "schema.yaml"
    if not schema_file.exists():
        schema_file.write_text(_schema_yaml(), encoding="utf-8")

    template_file = template_dir / "lane.md"
    if not template_file.exists():
        template_file.write_text(_lane_template(), encoding="utf-8")

    return schema_dir


def _schema_yaml() -> str:
    return """name: lane-lite
version: 1
description: Minimal lane spec for small fixes, docs, chores, and tests
artifacts:
  - id: lane
    generates: lane.md
    description: Compact intent, acceptance, and task record
    template: lane.md
    instruction: |
      Create a compact lane record that explains why the change exists, what is
      in scope, how acceptance will be judged, and the implementation tasks.
    requires: []

apply:
  requires: [lane]
  tracks: lane.md
"""


def _lane_template() -> str:
    return """# Lane: <change-id>

## Intent

## Scope

## Acceptance

## Tasks

- [ ]
"""
