from __future__ import annotations

from pathlib import Path

from lane.init import ensure_lane_ignored, install_lane_lite_schema


def test_ensure_lane_ignored_creates_gitignore(tmp_path: Path) -> None:
    ensure_lane_ignored(tmp_path)

    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == ".lane/\n"


def test_ensure_lane_ignored_appends_once(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("dist/\n", encoding="utf-8")

    ensure_lane_ignored(tmp_path)
    ensure_lane_ignored(tmp_path)

    assert gitignore.read_text(encoding="utf-8") == "dist/\n.lane/\n"


def test_install_lane_lite_schema(tmp_path: Path) -> None:
    schema_dir = install_lane_lite_schema(tmp_path)

    assert schema_dir == tmp_path / ".local/share/openspec/schemas/lane-lite"
    assert (schema_dir / "schema.yaml").exists()
    assert (schema_dir / "templates/lane.md").exists()
