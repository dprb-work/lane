from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

LANE_IGNORE_ENTRY = ".lane/"
LANE_LITE_SCHEMA = "lane-lite"
MIN_PASEO_VERSION = "0.1.75"
PASEO_NPM_PACKAGE = "@getpaseo/cli"
REQUIRED_TOOLS = ("paseo", "openspec", "git", "gh", "glab", "just")


class InitError(RuntimeError):
    pass


@dataclass(frozen=True)
class InitResult:
    gitignore: Path
    schema_dir: Path
    missing_tools: tuple[str, ...]
    paseo_version: str | None
    paseo_current_version: str | None
    paseo_upgrade_hint: str | None


def run_init(target: Path, *, home: Path | None = None) -> InitResult:
    target = target.resolve()
    ensure_lane_ignored(target)
    schema_dir = install_lane_lite_schema(Path.home() if home is None else home)
    paseo_check = check_paseo_cli(target)
    missing_tools = tuple(
        tool
        for tool in REQUIRED_TOOLS
        if (tool == "paseo" and paseo_check.version is None)
        or (tool != "paseo" and shutil.which(tool) is None)
    )
    return InitResult(
        gitignore=target / ".gitignore",
        schema_dir=schema_dir,
        missing_tools=missing_tools,
        paseo_version=paseo_check.version,
        paseo_current_version=paseo_check.current_version,
        paseo_upgrade_hint=paseo_check.upgrade_hint,
    )


@dataclass(frozen=True)
class PaseoCliCheck:
    version: str | None
    current_version: str | None
    upgrade_hint: str | None


def check_paseo_cli(target: Path) -> PaseoCliCheck:
    executable = shutil.which("paseo") or _local_paseo_bin(target)
    if executable is None:
        return PaseoCliCheck(version=None, current_version=None, upgrade_hint=None)

    current_version = _current_paseo_version()
    result = subprocess.run(
        [executable, "--version"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return PaseoCliCheck(
            version=None,
            current_version=current_version,
            upgrade_hint="paseo CLI is present but `paseo --version` failed",
        )

    version = result.stdout.strip() or result.stderr.strip()
    if _version_tuple(version) < _version_tuple(MIN_PASEO_VERSION):
        raise InitError(
            f"paseo CLI {version} is below required minimum {MIN_PASEO_VERSION}"
        )

    upgrade_hint = None
    if current_version is not None and _version_tuple(version) < _version_tuple(
        current_version
    ):
        upgrade_hint = (
            f"paseo CLI {version} is older than current {current_version}; "
            f"consider upgrading {PASEO_NPM_PACKAGE}"
        )
    return PaseoCliCheck(
        version=version,
        current_version=current_version,
        upgrade_hint=upgrade_hint,
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


def _local_paseo_bin(target: Path) -> str | None:
    path = target / "node_modules" / ".bin" / "paseo"
    if path.exists():
        return str(path)
    return None


def _current_paseo_version() -> str | None:
    if shutil.which("npm") is None:
        return None
    result = subprocess.run(
        ["npm", "view", PASEO_NPM_PACKAGE, "version"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    version = result.stdout.strip()
    return version or None


def _version_tuple(version: str) -> tuple[int, int, int]:
    parts = version.split(".")[:3]
    numbers: list[int] = []
    for part in parts:
        digits = ""
        for char in part:
            if not char.isdigit():
                break
            digits += char
        numbers.append(int(digits or "0"))
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


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
