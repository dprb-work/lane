from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lane.branches import supported_branch_types_label
from lane.init import (
    AGENT_INSTRUCTIONS,
    AGENT_INSTRUCTIONS_HEADER,
    CODEX_SKILL_MARKER,
    OPENCODE_TOOL_PLACEHOLDER,
    SHARED_VENV_SETUP_COMMAND,
    InitError,
    check_paseo_cli,
    codex_skill_path,
    compact_codex_skill_note,
    compact_tool_requirement_note,
    ensure_agent_instructions,
    ensure_codex_skill,
    ensure_lane_ignored,
    ensure_opencode_tool_registration,
    ensure_paseo_shared_venv_setup,
    install_lane_lite_schema,
    opencode_tool_path,
    run_init,
    run_install,
)


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


def test_run_init_reports_required_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lane.init.shutil.which",
        lambda tool: "/usr/bin/tool" if tool in {"git", "paseo"} else None,
    )
    monkeypatch.setattr(
        "lane.init.subprocess.run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "0.1.75\n", ""),
    )

    result = run_init(tmp_path, home=tmp_path)

    assert result.missing_tools == ("openspec", "gh", "glab")
    assert result.paseo_config == tmp_path / "paseo.json"
    assert not (tmp_path / ".local/share/openspec/schemas/lane-lite").exists()


def test_run_install_reports_user_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: None)

    result = run_install(home=tmp_path)

    assert result.schema_dir == tmp_path / ".local/share/openspec/schemas/lane-lite"
    assert result.opencode_tool == tmp_path / ".config/opencode/tools/lane.ts"
    assert result.opencode_tool_action == "skipped"
    assert result.codex_skill == tmp_path / ".agents/skills/lane/SKILL.md"
    assert result.codex_skill_action == "skipped"


def test_agent_instructions_list_supported_branch_types() -> None:
    assert f"Supported types: {supported_branch_types_label()}." in AGENT_INSTRUCTIONS


def test_ensure_paseo_shared_venv_setup_creates_config(tmp_path: Path) -> None:
    action = ensure_paseo_shared_venv_setup(tmp_path)

    raw = json.loads((tmp_path / "paseo.json").read_text(encoding="utf-8"))
    assert action == "created"
    assert raw["worktree"]["setup"][0].startswith("# lane:shared-venv")


def test_ensure_paseo_shared_venv_setup_appends_once(tmp_path: Path) -> None:
    path = tmp_path / "paseo.json"
    path.write_text(
        json.dumps(
            {
                "worktree": {"setup": "npm ci"},
                "scripts": {"test": {"command": "npm test"}},
            }
        ),
        encoding="utf-8",
    )

    assert ensure_paseo_shared_venv_setup(tmp_path) == "updated"
    assert ensure_paseo_shared_venv_setup(tmp_path) == "unchanged"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["worktree"]["setup"][0] == "npm ci"
    assert raw["worktree"]["setup"][1].startswith("# lane:shared-venv")
    assert raw["scripts"] == {"test": {"command": "npm test"}}


def test_ensure_paseo_shared_venv_setup_updates_stale_managed_command(
    tmp_path: Path,
) -> None:
    path = tmp_path / "paseo.json"
    path.write_text(
        json.dumps(
            {
                "worktree": {
                    "setup": [
                        "npm ci",
                        "# lane:shared-venv\nprintf 'old command\\n'",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    assert ensure_paseo_shared_venv_setup(tmp_path) == "updated"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["worktree"]["setup"] == ["npm ci", SHARED_VENV_SETUP_COMMAND]


def test_ensure_paseo_shared_venv_setup_rejects_invalid_config(
    tmp_path: Path,
) -> None:
    (tmp_path / "paseo.json").write_text("[]", encoding="utf-8")

    with pytest.raises(InitError, match="root must be an object"):
        ensure_paseo_shared_venv_setup(tmp_path)


def test_compact_tool_requirement_note_explains_provider_specific_clis() -> None:
    note = compact_tool_requirement_note()

    assert "GitHub repos need gh" in note
    assert "GitLab repos need glab" in note
    assert "do not need both" in note


def test_ensure_opencode_tool_registration_creates_global_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.ts"
    source.write_text(f"root={OPENCODE_TOOL_PLACEHOLDER}\n", encoding="utf-8")
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: "/bin/opencode")
    monkeypatch.setattr("lane.init.opencode_tool_source_path", lambda: source)

    action = ensure_opencode_tool_registration(home=tmp_path)

    path = opencode_tool_path(home=tmp_path)
    assert action == "created"
    assert OPENCODE_TOOL_PLACEHOLDER not in path.read_text(encoding="utf-8")


def test_ensure_opencode_tool_registration_skips_when_opencode_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: None)

    action = ensure_opencode_tool_registration(home=tmp_path)

    assert action == "skipped"
    assert not opencode_tool_path(home=tmp_path).exists()


def test_ensure_codex_skill_creates_managed_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: "/bin/codex")

    action = ensure_codex_skill(home=tmp_path)

    path = codex_skill_path(home=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert action == "created"
    assert path == tmp_path / ".agents/skills/lane/SKILL.md"
    assert "name: lane" in text
    assert CODEX_SKILL_MARKER in text
    assert "lane start <type>/<slug>" in text


def test_ensure_codex_skill_replaces_managed_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: "/bin/codex")
    path = codex_skill_path(home=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(f"old\n{CODEX_SKILL_MARKER}\n", encoding="utf-8")

    action = ensure_codex_skill(home=tmp_path)

    assert action == "replaced"
    assert "old" not in path.read_text(encoding="utf-8")


def test_ensure_codex_skill_skips_custom_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: "/bin/codex")
    path = codex_skill_path(home=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: lane\n---\ncustom\n", encoding="utf-8")

    action = ensure_codex_skill(home=tmp_path)

    assert action == "skipped"
    assert "custom" in path.read_text(encoding="utf-8")


def test_ensure_codex_skill_skips_when_codex_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: None)

    action = ensure_codex_skill(home=tmp_path)

    assert action == "skipped"
    assert not codex_skill_path(home=tmp_path).exists()


def test_compact_codex_skill_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda tool: "/bin/codex")
    monkeypatch.setattr("lane.init.codex_skill_path", lambda: tmp_path / "SKILL.md")

    assert compact_codex_skill_note(tmp_path) == "install codex skill: lane install"

    (tmp_path / "SKILL.md").write_text(CODEX_SKILL_MARKER, encoding="utf-8")

    assert compact_codex_skill_note(tmp_path).startswith("codex skill present:")


def test_ensure_agent_instructions_creates_agents(tmp_path: Path) -> None:
    action = ensure_agent_instructions(tmp_path)

    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert action == "created"
    assert text.startswith("# Lane Agent Instructions")
    assert "Mandatory Lane Workflow" in text
    assert "Paseo owns workspace and worktree creation" in text


def test_ensure_agent_instructions_appends_to_existing_agents(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Existing\n\nKeep this.\n", encoding="utf-8")

    action = ensure_agent_instructions(tmp_path)

    text = agents.read_text(encoding="utf-8")
    assert action == "updated"
    assert text.startswith("# Existing\n\nKeep this.")
    assert text.count(AGENT_INSTRUCTIONS_HEADER) == 1


def test_ensure_agent_instructions_replaces_existing_managed_block(
    tmp_path: Path,
) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "# Existing\n\n"
        "<!-- lane:instructions:start -->\n"
        "old instructions\n"
        "<!-- lane:instructions:end -->\n\n"
        "After.\n",
        encoding="utf-8",
    )

    action = ensure_agent_instructions(tmp_path)

    text = agents.read_text(encoding="utf-8")
    assert action == "replaced"
    assert "old instructions" not in text
    assert "Mandatory Lane Workflow" in text
    assert "After." in text
    assert text.count(AGENT_INSTRUCTIONS_HEADER) == 1


def test_check_paseo_cli_reports_version(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda _: "/usr/bin/paseo")
    monkeypatch.setattr(
        "lane.init.subprocess.run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "0.1.75\n", ""),
    )

    result = check_paseo_cli(tmp_path)

    assert result.version == "0.1.75"
    assert result.current_version == "0.1.75"
    assert result.upgrade_hint is None


def test_check_paseo_cli_rejects_below_minimum(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda _: "/usr/bin/paseo")
    monkeypatch.setattr(
        "lane.init.subprocess.run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "0.1.0\n", ""),
    )

    with pytest.raises(InitError, match="below required minimum"):
        check_paseo_cli(tmp_path)


def test_check_paseo_cli_reports_upgrade_hint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("lane.init.shutil.which", lambda _: "/usr/bin/paseo")

    def fake_run(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if argv[:3] == ["npm", "view", "@getpaseo/cli"]:
            return subprocess.CompletedProcess(argv, 0, "0.1.76\n", "")
        return subprocess.CompletedProcess(argv, 0, "0.1.75\n", "")

    monkeypatch.setattr("lane.init.subprocess.run", fake_run)

    result = check_paseo_cli(tmp_path)

    assert result.version == "0.1.75"
    assert result.current_version == "0.1.76"
    assert result.upgrade_hint is not None


def test_check_paseo_cli_uses_local_node_modules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    local_bin = tmp_path / "node_modules" / ".bin" / "paseo"
    local_bin.parent.mkdir(parents=True)
    local_bin.write_text("", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "lane.init.shutil.which",
        lambda tool: None if tool == "paseo" else "/usr/bin/npm",
    )

    def fake_run(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "0.1.75\n", "")

    monkeypatch.setattr("lane.init.subprocess.run", fake_run)

    result = check_paseo_cli(tmp_path)

    assert result.version == "0.1.75"
    assert calls == [
        ["npm", "view", "@getpaseo/cli", "version"],
        [str(local_bin), "--version"],
    ]
