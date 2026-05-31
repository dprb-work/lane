from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from lane.branches import supported_branch_types_label
from lane.verify import VerifyError, discover_verify_command

LANE_IGNORE_ENTRY = ".lane/"
LANE_LITE_SCHEMA = "lane-lite"
MIN_PASEO_VERSION = "0.1.75"
PASEO_NPM_PACKAGE = "@getpaseo/cli"
REPORTED_TOOLS = ("paseo", "openspec", "git", "gh", "glab")
AGENT_INSTRUCTIONS_HEADER = "<!-- lane:instructions:start -->"
AGENT_INSTRUCTIONS_FOOTER = "<!-- lane:instructions:end -->"
CODEX_SKILL_MARKER = "<!-- lane:codex-skill -->"
OPENCODE_TOOL_PLACEHOLDER = "__LANE_REPO_ROOT__"
PASEO_CONFIG_FILE = "paseo.json"
SHARED_VENV_SETUP_MARKER = "# lane:shared-venv"
SHARED_VENV_SETUP_COMMAND = """# lane:shared-venv
if [ -d "$PASEO_SOURCE_CHECKOUT_PATH/.venv" ]; then
  if [ -e "$PASEO_WORKTREE_PATH/.venv" ] && [ ! -L "$PASEO_WORKTREE_PATH/.venv" ]; then
    printf 'lane shared venv target exists and is not a symlink: %s\n' \
      "$PASEO_WORKTREE_PATH/.venv" >&2
  else
    ln -sfn "$PASEO_SOURCE_CHECKOUT_PATH/.venv" "$PASEO_WORKTREE_PATH/.venv"
  fi
else
  printf 'lane shared venv missing: %s\n' "$PASEO_SOURCE_CHECKOUT_PATH/.venv" >&2
fi"""

VERIFICATION_SETUP_NOTE = """Verification setup:

- Repository verification is not configured yet; `lane init` does not create a
  no-op verifier.
- A developer agent should add one real repo-owned verification entrypoint:
  `scripts/verify.py` when Python is already a repo/runtime dependency,
  `just verify` when the repo uses Just, or `npm run verify` when the repo is
  Node/npm-based.
- The verifier should run the meaningful checks for the repo and fail when those
  checks fail or required verification tools are missing. A logging-only or empty
  verifier is not acceptable because it makes unverified work appear verified.
- After adding the verifier, run `lane init` again or remove this setup note from
  the Lane-managed AGENTS.md block.

"""


def agent_instructions(*, verification_configured: bool) -> str:
    verification_setup = "" if verification_configured else VERIFICATION_SETUP_NOTE
    return f"""{AGENT_INSTRUCTIONS_HEADER}
## Mandatory Lane Workflow

This repository uses `lane` as the required Paseo-native lifecycle workflow.
Agents MUST use `lane` commands and Paseo-owned workspaces for task work in this
repository.

Paseo owns workspace and worktree creation, setup, services, provider runtimes,
agents, terminals, and archive behavior. `lane` owns the compact lifecycle policy
around one coherent line of work: ignored `.lane/` state, required OpenSpec specs,
verification, review orchestration, finalize, cleanup, and abort.

Do not create, switch, push, finalize, or clean up task work with raw
`git worktree`, raw `git push`, or ad hoc checkout commands. Use the `lane` CLI
instead. The only allowed exceptions are when the user explicitly instructs you
to bypass `lane`, or when `lane` and Paseo are unavailable. If an exception
applies, state it before using raw Git or the source checkout.

Required commands:

- Initialize repo support with `lane init`.
- Start Paseo-backed lanes with `lane start <type>/<slug>`.
  Supported types: {supported_branch_types_label()}.
- Inspect work with `lane status` and `lane list`.
- Verify with `lane verify`.
- Run lane-scoped commands with `lane run -- <command>`.
- Run review perspectives with `lane review`.
- Prepare PR handoff with `lane finalize`.
- Retire merged or canceled lanes with `lane cleanup` or `lane abort`.

{verification_setup}

OpenCode, Codex, Claude Code, and other runtimes are provider implementations
behind Paseo. Keep provider-specific assumptions out of repo-local workflow
policy unless the user explicitly asks for them.
{AGENT_INSTRUCTIONS_FOOTER}
"""


AGENT_INSTRUCTIONS = agent_instructions(verification_configured=False)


class InitError(RuntimeError):
    pass


@dataclass(frozen=True)
class InitResult:
    gitignore: Path
    agents: Path
    agents_action: str
    paseo_config: Path
    paseo_config_action: str
    missing_tools: tuple[str, ...]
    paseo_version: str | None
    paseo_current_version: str | None
    paseo_upgrade_hint: str | None
    verification_command: str | None


@dataclass(frozen=True)
class InstallResult:
    opencode_tool: Path
    opencode_tool_action: str
    codex_skill: Path
    codex_skill_action: str
    schema_dir: Path


def run_install(*, home: Path | None = None) -> InstallResult:
    home_root = Path.home() if home is None else home
    return run_install_for_paths(
        home=home_root,
        opencode_tool=opencode_tool_path(home=home_root),
        codex_skill=codex_skill_path(home=home_root),
        schema_dir=lane_lite_schema_path(home=home_root),
    )


def run_install_for_paths(
    *,
    home: Path,
    opencode_tool: Path,
    codex_skill: Path,
    schema_dir: Path,
) -> InstallResult:
    return InstallResult(
        opencode_tool=opencode_tool,
        opencode_tool_action=ensure_opencode_tool_registration(
            home=home,
            path=opencode_tool,
        ),
        codex_skill=codex_skill,
        codex_skill_action=ensure_codex_skill(path=codex_skill),
        schema_dir=install_lane_lite_schema(schema_dir=schema_dir),
    )


def run_init(target: Path, *, home: Path | None = None) -> InitResult:
    target = target.resolve()
    verification_command = configured_verify_command(target)
    ensure_lane_ignored(target)
    agents_action = ensure_agent_instructions(
        target,
        verification_configured=verification_command is not None,
    )
    paseo_config_action = ensure_paseo_shared_venv_setup(target)
    paseo_check = check_paseo_cli(target)
    missing_tools = tuple(
        tool
        for tool in REPORTED_TOOLS
        if (tool == "paseo" and paseo_check.version is None)
        or (tool != "paseo" and shutil.which(tool) is None)
    )
    return InitResult(
        gitignore=target / ".gitignore",
        agents=target / "AGENTS.md",
        agents_action=agents_action,
        paseo_config=target / PASEO_CONFIG_FILE,
        paseo_config_action=paseo_config_action,
        missing_tools=missing_tools,
        paseo_version=paseo_check.version,
        paseo_current_version=paseo_check.current_version,
        paseo_upgrade_hint=paseo_check.upgrade_hint,
        verification_command=verification_command,
    )


def opencode_tool_path(*, home: Path | None = None) -> Path:
    if home is None:
        return Path("~/.config/opencode/tools/lane.ts").expanduser()
    return home / ".config" / "opencode" / "tools" / "lane.ts"


def lane_lite_schema_path(*, home: Path | None = None) -> Path:
    if home is None:
        home = Path.home()
    return home / ".local" / "share" / "openspec" / "schemas" / LANE_LITE_SCHEMA


def compact_opencode_registration_note() -> str:
    if shutil.which("opencode") is None:
        return "opencode tool skipped: opencode not found on PATH"
    path = opencode_tool_path()
    if path.is_file():
        return f"opencode tool present: {path}"
    return "install opencode tool: lane install"


def codex_skill_path(*, home: Path | None = None) -> Path:
    if home is None:
        return Path("~/.agents/skills/lane/SKILL.md").expanduser()
    return home / ".agents" / "skills" / "lane" / "SKILL.md"


def compact_codex_skill_note(target: Path) -> str:
    if shutil.which("codex") is None:
        return "codex skill skipped: codex not found on PATH"
    path = codex_skill_path()
    if path.is_file():
        return f"codex skill present: {path}"
    return "install codex skill: lane install"


def compact_tool_requirement_note() -> str:
    return (
        "tool note: gh and glab are provider-specific; GitHub repos need gh, "
        "GitLab repos need glab, and you do not need both for one provider"
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


def configured_verify_command(target: Path) -> str | None:
    try:
        return discover_verify_command(target).label
    except VerifyError:
        return None


def ensure_agent_instructions(
    target: Path,
    *,
    verification_configured: bool = False,
) -> str:
    path = target / "AGENTS.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    instructions = agent_instructions(verification_configured=verification_configured)

    start = existing.find(AGENT_INSTRUCTIONS_HEADER)
    end = existing.find(AGENT_INSTRUCTIONS_FOOTER)
    if start != -1 and end != -1 and end > start:
        end += len(AGENT_INSTRUCTIONS_FOOTER)
        updated = existing[:start].rstrip() + "\n\n" + instructions
        suffix = existing[end:].strip()
        if suffix:
            updated += "\n\n" + suffix
        path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return "replaced"

    if existing.strip():
        path.write_text(
            existing.rstrip() + "\n\n" + instructions + "\n",
            encoding="utf-8",
        )
        return "updated"

    path.write_text(
        "# Lane Agent Instructions\n\n" + instructions + "\n",
        encoding="utf-8",
    )
    return "created"


def ensure_opencode_tool_registration(
    *,
    home: Path | None = None,
    path: Path | None = None,
) -> str:
    if shutil.which("opencode") is None:
        return "skipped"

    path = opencode_tool_path(home=home) if path is None else path
    content = _asset_text("assets/opencode/tools/lane.ts").replace(
        OPENCODE_TOOL_PLACEHOLDER,
        str(Path(__file__).resolve().parents[2]),
    )
    if path.exists() or path.is_symlink():
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if existing == content and not path.is_symlink():
            return "unchanged"
        path.unlink()
        action = "replaced"
    else:
        action = "created"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return action


def ensure_codex_skill(
    *,
    home: Path | None = None,
    path: Path | None = None,
) -> str:
    if shutil.which("codex") is None:
        return "skipped"
    path = codex_skill_path(home=home) if path is None else path
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if CODEX_SKILL_MARKER not in existing:
            return "skipped"
        skill = _codex_skill()
        if existing == skill:
            return "unchanged"
        path.write_text(skill, encoding="utf-8")
        return "replaced"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_codex_skill(), encoding="utf-8")
    return "created"


def ensure_paseo_shared_venv_setup(target: Path) -> str:
    path = target / PASEO_CONFIG_FILE
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise InitError(f"invalid paseo.json: {error}") from error
        if not isinstance(raw, dict):
            raise InitError("invalid paseo.json: root must be an object")
        config = raw
        action = "updated"
    else:
        config = {}
        action = "created"

    worktree = config.get("worktree")
    if worktree is None:
        worktree = {}
        config["worktree"] = worktree
    if not isinstance(worktree, dict):
        raise InitError("invalid paseo.json: worktree must be an object")

    setup = _normalize_setup_commands(worktree.get("setup"))
    managed_indexes = [
        index
        for index, command in enumerate(setup)
        if SHARED_VENV_SETUP_MARKER in command
    ]
    if (
        len(managed_indexes) == 1
        and setup[managed_indexes[0]] == SHARED_VENV_SETUP_COMMAND
    ):
        return "unchanged"

    if managed_indexes:
        managed_index = managed_indexes[0]
        setup = [
            command
            for command in setup
            if SHARED_VENV_SETUP_MARKER not in command
        ]
        setup.insert(managed_index, SHARED_VENV_SETUP_COMMAND)
        worktree["setup"] = setup
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return "updated"

    worktree["setup"] = [*setup, SHARED_VENV_SETUP_COMMAND]
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return action


def _normalize_setup_commands(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        commands: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise InitError(
                    "invalid paseo.json: worktree.setup must contain strings"
                )
            if item.strip():
                commands.append(item)
        return commands
    raise InitError("invalid paseo.json: worktree.setup must be a string or array")


def install_lane_lite_schema(
    home: Path | None = None,
    *,
    schema_dir: Path | None = None,
) -> Path:
    if schema_dir is None:
        schema_dir = lane_lite_schema_path(home=home)
    source = files("lane").joinpath(f"assets/openspec/schemas/{LANE_LITE_SCHEMA}")
    with as_file(source) as source_path:
        shutil.copytree(source_path, schema_dir, dirs_exist_ok=True)
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


def _codex_skill() -> str:
    return _asset_text("assets/codex/skills/lane/SKILL.md")


def _asset_text(path: str) -> str:
    return files("lane").joinpath(path).read_text(encoding="utf-8")
