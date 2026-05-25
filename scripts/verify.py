from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    ruff = subprocess.run([sys.executable, "-m", "ruff", "check", "."], check=False)
    if ruff.returncode != 0:
        return ruff.returncode

    env = os.environ.copy()
    env["PYTHONPATH"] = _prepend_pythonpath("src", env.get("PYTHONPATH"))
    pytest = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        check=False,
        env=env,
    )
    return pytest.returncode


def _prepend_pythonpath(path: str, existing: str | None) -> str:
    if not existing:
        return path
    return os.pathsep.join((path, existing))


if __name__ == "__main__":
    raise SystemExit(main())
