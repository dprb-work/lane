from __future__ import annotations

import argparse
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_config_dir() -> Path:
    return Path("~/.config/opencode/tools").expanduser()


def copy_tool_definition(*, root: Path, config_dir: Path) -> list[str]:
    source = root / "opencode" / "tools" / "lane.ts"
    target = config_dir.expanduser() / "lane.ts"
    actions = [f"opencode source: {source}", f"opencode target: {target}"]
    if not source.is_file():
        raise FileNotFoundError(f"missing opencode source: {source}")

    content = source.read_text(encoding="utf-8").replace(
        "__LANE_REPO_ROOT__",
        str(root),
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
        actions.append(
            "opencode: replaced existing tool definition; restart OpenCode to refresh"
        )
    target.write_text(content, encoding="utf-8")
    actions.append("opencode: copied")
    actions.append("status: installed")
    return actions


def install(*, config_dir: Path) -> list[str]:
    root = repo_root()
    actions = [f"repo: {root}"]
    actions.extend(copy_tool_definition(root=root, config_dir=config_dir))
    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register the lane OpenCode custom tool definition."
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=default_config_dir(),
        help="OpenCode tools directory (default: ~/.config/opencode/tools).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    for action in install(config_dir=args.config_dir):
        print(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
