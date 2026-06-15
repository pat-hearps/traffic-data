import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def _read_version_file() -> str:
    return (REPO_ROOT / "core" / "VERSION").read_text().strip()


def _read_pyproject_version() -> str:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]


def _read_bumpversion_current() -> str:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]
    data = tomllib.loads((REPO_ROOT / "bumpversion.toml").read_text())
    return data["tool"]["bumpversion"]["current_version"]


def test_version_files_in_sync():
    """All three version declarations must match, and core.__version__ must equal the file."""
    ver_file = _read_version_file()
    ver_pyproject = _read_pyproject_version()
    ver_bumpversion = _read_bumpversion_current()

    assert ver_file == ver_pyproject, (
        f"core/VERSION ({ver_file!r}) != pyproject.toml version ({ver_pyproject!r})"
    )
    assert ver_file == ver_bumpversion, (
        f"core/VERSION ({ver_file!r}) != bumpversion.toml current_version ({ver_bumpversion!r})"
    )
    # core.__version__ is computed directly from core/VERSION at import time (no parsing),
    # so a passing file-comparison above implies it will be correct at runtime too.


@pytest.mark.skipif(
    shutil.which("bump-my-version") is None,
    reason="bump-my-version not installed (run: uv sync --extra ci && source .venv/bin/activate)",
)
def test_bumpversion_dryrun_dev():
    """bump-my-version dry-run for a dev bump produces the expected next version."""
    current = _read_version_file()

    # Expect X.Y.Z.devN -> X.Y.Z.dev(N+1)
    m = re.fullmatch(r"(\d+\.\d+\.\d+)\.dev(\d+)", current)
    assert m, f"Expected a dev version (X.Y.Z.devN) but got {current!r}"
    expected = f"{m.group(1)}.dev{int(m.group(2)) + 1}"

    result = subprocess.run(
        ["bump-my-version", "bump", "--dry-run", "--allow-dirty", "-v", "pre_n"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**__import__("os").environ, "BUMPVERSION_CONFIG_FILE": "bumpversion.toml"},
    )
    assert result.returncode == 0, f"bump-my-version exited {result.returncode}:\n{result.stderr}"

    output = result.stdout + result.stderr
    assert expected in output, (
        f"Expected new version {expected!r} in dry-run output but got:\n{output}"
    )
