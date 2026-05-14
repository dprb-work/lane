from __future__ import annotations

import importlib.util
from pathlib import Path


def load_register_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "register_opencode_tool.py"
    spec = importlib.util.spec_from_file_location("register_opencode_tool", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


register = load_register_module()


def test_copy_tool_definition_replaces_existing_target(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "opencode" / "tools" / "lane.ts"
    source.parent.mkdir(parents=True)
    source.write_text("root=__LANE_REPO_ROOT__\n", encoding="utf-8")
    config_dir = tmp_path / "config"
    target = config_dir / "lane.ts"
    target.parent.mkdir(parents=True)
    target.write_text("old\n", encoding="utf-8")

    actions = register.copy_tool_definition(root=root, config_dir=config_dir)

    assert target.read_text(encoding="utf-8") == f"root={root}\n"
    assert (
        "opencode: replaced existing tool definition; restart OpenCode to refresh"
        in actions
    )
    assert "opencode: copied" in actions


def test_copy_tool_definition_replaces_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "opencode" / "tools" / "lane.ts"
    source.parent.mkdir(parents=True)
    source.write_text("tool\n", encoding="utf-8")
    config_dir = tmp_path / "config"
    old_target = tmp_path / "old.ts"
    old_target.write_text("old\n", encoding="utf-8")
    target = config_dir / "lane.ts"
    target.parent.mkdir(parents=True)
    target.symlink_to(old_target)

    register.copy_tool_definition(root=root, config_dir=config_dir)

    assert target.read_text(encoding="utf-8") == "tool\n"
    assert not target.is_symlink()


def test_copy_tool_definition_creates_missing_target(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "opencode" / "tools" / "lane.ts"
    source.parent.mkdir(parents=True)
    source.write_text("tool\n", encoding="utf-8")
    config_dir = tmp_path / "config"

    actions = register.copy_tool_definition(root=root, config_dir=config_dir)

    assert (config_dir / "lane.ts").read_text(encoding="utf-8") == "tool\n"
    assert "opencode: copied" in actions
    assert "status: installed" in actions
