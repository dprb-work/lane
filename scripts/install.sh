#!/usr/bin/env bash
set -euo pipefail

PASEO_PACKAGE="@getpaseo/cli"
OPENSPEC_PACKAGE="@fission-ai/openspec"
NPM_PREFIX="${NPM_PREFIX:-$HOME/.local/opt/node}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
VENV_DIR="${VENV_DIR:-.venv}"

assume_yes=0
dev=0

usage() {
  printf 'Usage: %s [--yes] [--dev]\n' "$0"
  printf '\n'
  printf 'Installs required lane dependencies:\n'
  printf '  system tools: git, gh, glab, just, npm, python3\n'
  printf '  npm CLIs: %s, %s into %s\n' "$PASEO_PACKAGE" "$OPENSPEC_PACKAGE" "$NPM_PREFIX"
  printf '  Python package: lane%s into %s\n' ' (editable)' "$VENV_DIR"
  printf '  executable links in: %s\n' "$BIN_DIR"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes|-y)
      assume_yes=1
      ;;
    --dev)
      dev=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

confirm() {
  if [ "$assume_yes" -eq 1 ]; then
    return 0
  fi
  printf 'Install required lane dependencies on this machine? [y/N] '
  read -r answer
  case "$answer" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      printf 'aborted\n'
      exit 1
      ;;
  esac
}

have() {
  command -v "$1" >/dev/null 2>&1
}

sudo_prefix() {
  if [ "$(id -u)" -eq 0 ]; then
    return 0
  fi
  if have sudo; then
    printf 'sudo'
    return 0
  fi
  printf 'Missing sudo; rerun as root or install missing system tools manually.\n' >&2
  exit 1
}

install_system_tools() {
  missing=""
  for tool in git gh glab just npm python3; do
    if ! have "$tool"; then
      missing="$missing $tool"
    fi
  done

  if [ -z "$missing" ]; then
    printf 'system tools: already installed\n'
    return 0
  fi

  printf 'system tools missing:%s\n' "$missing"

  if have apt-get; then
    sudo_cmd="$(sudo_prefix)"
    # shellcheck disable=SC2086
    $sudo_cmd apt-get update
    # shellcheck disable=SC2086
    $sudo_cmd apt-get install -y git gh glab just npm python3 python3-venv
    return 0
  fi

  if have brew; then
    brew install git gh glab just node python
    return 0
  fi

  if have dnf; then
    sudo_cmd="$(sudo_prefix)"
    # shellcheck disable=SC2086
    $sudo_cmd dnf install -y git gh glab just npm python3
    return 0
  fi

  if have pacman; then
    sudo_cmd="$(sudo_prefix)"
    # shellcheck disable=SC2086
    $sudo_cmd pacman -Sy --needed --noconfirm git github-cli glab just npm python
    return 0
  fi

  printf 'No supported package manager found. Install manually:%s\n' "$missing" >&2
  exit 1
}

install_node_clis() {
  if ! have npm; then
    printf 'npm is required after system tool installation but is still missing\n' >&2
    exit 1
  fi

  mkdir -p "$NPM_PREFIX" "$BIN_DIR"
  npm install
  npm install --prefix "$NPM_PREFIX" -g "$PASEO_PACKAGE" "$OPENSPEC_PACKAGE"
  link_executable "$NPM_PREFIX/bin/paseo" "$BIN_DIR/paseo"
  link_executable "$NPM_PREFIX/bin/openspec" "$BIN_DIR/openspec"
}

install_python_package() {
  if ! have python3; then
    printf 'python3 is required after system tool installation but is still missing\n' >&2
    exit 1
  fi

  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip

  if [ "$dev" -eq 1 ]; then
    "$VENV_DIR/bin/python" -m pip install -e ".[dev]"
  else
    "$VENV_DIR/bin/python" -m pip install -e .
  fi

  mkdir -p "$BIN_DIR"
  link_executable "$(pwd)/$VENV_DIR/bin/lane" "$BIN_DIR/lane"
}

link_executable() {
  source_path="$1"
  link_path="$2"
  if [ ! -e "$source_path" ]; then
    printf 'Expected executable not found: %s\n' "$source_path" >&2
    exit 1
  fi
  ln -sfn "$source_path" "$link_path"
}

report_versions() {
  printf '\nInstalled versions:\n'
  for cmd in git gh glab just npm python3 paseo openspec lane; do
    if have "$cmd"; then
      printf '  %s: ' "$cmd"
      "$cmd" --version | sed -n '1p'
    else
      printf '  %s: missing\n' "$cmd"
    fi
  done
}

confirm
install_system_tools
install_node_clis
install_python_package
report_versions

printf '\nlane dependencies installed. Run `lane init` inside a target repo to bootstrap lane state.\n'
printf 'Ensure %s is on PATH for paseo, openspec, and lane.\n' "$BIN_DIR"
