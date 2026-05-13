from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.init import (
    InitError,
    check_paseo_cli,
    ensure_lane_ignored,
    install_lane_lite_schema,
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
