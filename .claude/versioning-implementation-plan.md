# Versioning System — Implementation Plan

> **Status:** Not yet implemented. This document is the complete, self-contained spec for
> adding a `bump-my-version`-based versioning system to this repo. It is written so an agent
> with **no prior chat context** and **no access to the source template repo** can execute it.
> All required file contents are embedded below verbatim.

## Context

This repo currently has only a static `version = "0.0.1"` in `pyproject.toml` and no mechanism
to manage or surface the version at runtime. This change ports a reusable versioning pattern
(originally from a sibling `ml-project-template` repo) that uses the
[`bump-my-version`](https://pypi.org/project/bump-my-version/) tool, driven by a branch-aware
shell wrapper, with the current version stored in a `core/VERSION` file that is read at import
time and printed when the `core` package loads.

### Decisions already made (do not re-litigate)

- **pyproject sync**: bumpversion updates `pyproject.toml`'s version field too, kept in sync with `core/VERSION`.
- **Starting version**: `0.0.1-dev1` (becomes `0.0.1.dev1` after the PEP 440 step — see Step 7).
- **Branch rules**: keep the template's `main`/`dev` rule verbatim — release from `main`, dev-bump from `dev`, fail on any other branch.
- **Version surfacing**: use a plain `print()` (NOT the project logger) inside `core/__init__.py`. (The original ask mentioned python logs, but this was overridden — keep `print`.)
- **PEP 440**: the final scheme must conform to PEP 440. This is applied as **Step 7 (final)** at
  the end of this plan, layered on top of the template-faithful port in Steps 1–6.

## Version scheme

Template-faithful form (Steps 1–6):
- **Dev version**: `{major}.{minor}.{patch}-dev{pre_n}` — e.g. `1.2.3-dev1`
- **Release version** (clean): `{major}.{minor}.{patch}` — e.g. `1.2.3`

PEP 440 form (after Step 7):
- **Dev version**: `{major}.{minor}.{patch}.dev{pre_n}` — e.g. `1.2.3.dev1` (dot separator, not dash)
- **Release version** (clean): `{major}.{minor}.{patch}` — unchanged

In both, the `pre_l` part has values `["dev", "final"]`; `final` is the hidden `optional_value`,
so a "final" release simply drops the dev suffix.

---

## Files to CREATE

### 1. `core/VERSION`

Single line of text:

```
0.0.1-dev1
```

> Note: only ONE `VERSION` file is needed — this repo has no `ml/` module (the source template
> tracked both `core/VERSION` and `ml/VERSION`; drop the `ml/` one).

### 2. `bumpversion.toml` (repo root)

Verbatim content to write:

```toml

# configurations for bump-my-version tool (handles package versioning)
# built from sample configs in docs: https://callowayproject.github.io/bump-my-version/tutorials/getting-started/

[tool.bumpversion]
current_version = "0.0.1-dev1"
parse = """(?x)                       # free-space / whitespace regex mode (allow multiline)
    (?P<major>0|[1-9]\\d*)\\.         # major component
    (?P<minor>0|[1-9]\\d*)\\.         # minor component
    (?P<patch>0|[1-9]\\d*)            # patch component
    (?:
        -                             # dash separator for pre-release section
        (?P<pre_l>[a-zA-Z-]+)         # pre-release label (str)
        (?P<pre_n>0|[1-9]\\d*)        # pre-release version number
    )?                                # pre-release section is optional
"""
serialize = [
    "{major}.{minor}.{patch}-{pre_l}{pre_n}",
    "{major}.{minor}.{patch}",
]
search = "{current_version}"
replace = "{new_version}"
regex = false
ignore_missing_version = false
ignore_missing_files = false
tag = true
sign_tags = false
tag_name = "{new_version}"
tag_message = "Bump version: {current_version} --> {new_version}"
allow_dirty = false
commit = true
message = "Bump version: {current_version} --> {new_version}"
commit_args = "--no-verify"  # i.e. don't run pre-commit hooks if any

[tool.bumpversion.parts.pre_l]
values = ["dev", "final"]
optional_value = "final"  # means that 'final' won't be shown/serialised

# need to separately specify each tracked file
[[tool.bumpversion.files]]
filename = "core/VERSION"

# also keep pyproject.toml's version field in sync. The scoped search/replace ensures only the
# [project] version line is rewritten, not any incidental match of the version string.
[[tool.bumpversion.files]]
filename = "pyproject.toml"
search = 'version = "{current_version}"'
replace = 'version = "{new_version}"'
```

### 3. `bin/bump.sh`

Create the directory `bin/` and write this file verbatim, then make it executable
(`chmod +x bin/bump.sh`):

```bash
#!/bin/bash

# Helper script using python package 'bump-my-version' with further constraints to
# allow for bumping project/package version number according to a set of rules
# see also https://pypi.org/project/bump-my-version/ and docs

# --- Script args ---
# call script either directly
# ./bin/bump.sh [ARG1]
# or with bash/source
# bash ./bin/bump.sh [ARG1]
# if provided, first positional argument (ARG1) will be used as version part to bump by,
# options: ['major', 'minor', 'patch', 'pre_n', 'dev']
# Arg can be left blank, in which case it defaults to 'dev'
# 'dev' is essentially an alias for 'pre_n', in that a dev bump will
# just increment the version number after the 'dev' suffix, e.g.
#   1.2.3-dev1  --> 1.2.3-dev2

# Context:
# A 'Dev' version number has the pattern with dev suffix: {major}.{minor}.{patch}-dev{pre_n}, e.g. 1.2.3-dev1
# A 'Release' version number has the 'clean' pattern:     {major}.{minor}.{patch},            e.g. 1.2.3

# Rules:
# - A bump from 'dev' branch will bump to a new -devX version number (same major/minor/patch)
# - A bump from 'main' branch will create a 'Release' version (just removes the -devX suffix
#   from the current major/minor/patch version number), followed immediately
#   by a patch bump to the next 'Dev' version
# - Bumping from any other branch will fail

# ================================== Script start ==================================
set -e  # stop if bad exit code occurs (otherwise may try to continue and push anyway)
export BUMPVERSION_CONFIG_FILE='./bumpversion.toml'

# (1) determine if we are on main or dev, and so whether to do a release or not
branch=$(git branch --show-current)

if [ $branch == "main" ]; then
    echo "Currently on main branch, bumping as release"
    do_release=1
elif [ $branch == "dev" ]; then
    echo "Currently on dev branch, bumping as development"
    do_release=0
else
    echo "Currently on branch '$branch', must be on 'main' or 'dev' to bump version"
    exit 1
fi


# (2) validate version argument
vers_arg=$1
vers_start=$(<core/VERSION)
echo "Starting at version $vers_start"

case $vers_arg in
    major|minor|patch|pre_n)
        echo "Will bump by '$vers_arg' version part"
        ;;
    pre_l)
        echo "Cannot bump by pre_level directly, this only use for a 'release' version from main"
        exit 1
        ;;
    dev)
        echo "Will bump by -devX version number only"
        vers_arg=pre_n
        ;;
    ?*)
        echo "Invalid version part to bump by: '$vers_arg'"
        exit 1
        ;;
    *)
        # if no arg, do same as 'pre_n', which is same as 'dev'
        echo "No version arg given, will bump by -devX version number only"
        vers_arg=pre_n
        ;;
esac

# (3) carry out bump version depending on inputs
base_cmd="bump-my-version bump "

if [ $do_release -eq 0 ]; then
    echo "Development version requested, just bumping by '$vers_arg' version part"
    $base_cmd --message "Dev bump: {current_version} --> {new_version}" $vers_arg

elif [ $do_release -eq 1 ]; then
    if [ $vers_arg = "major" ] || [ $vers_arg = "minor" ]; then
        echo "Intermediate '$vers_arg' bump as part of release"
        # we don't commit or tag here as it's only an intermediate step
        $base_cmd --no-commit --no-tag $vers_arg
        echo "Bumped to intermediate $(<core/VERSION)"
    elif [ $vers_arg = "pre_n" ]; then
        echo "Cannot bump by pre_number for a release version"
        exit 1
    else  # we don't actually increment patch version for a patch release, just bump pre_level (devX number)
        echo "Release version will have same maj.min.ptch number as starting dev version '$vers_start'"
    fi
    # then bump pre_l to create clean version - if $vers_arg was 'patch' this is all that's required
    echo "Bumping pre_level from dev to final (clean) for release"
    # this should increment from -devX to final (no dev).
    # --allow-dirty as we still have the intermediate major/minor dev bump sitting in the working dir
    $base_cmd --allow-dirty --message "Release bump: $vers_start --> {new_version}" pre_l
    echo " ==== Release version is '$(<core/VERSION)' ==== "
fi

# (4) If Release, follow up with an immediate dev bump
# also want to immediately move to patch dev version so there is no lingering code that
# contains the clean release tag (1.2.3) but is actually the next dev version (1.2.4-dev0)
# i.e. the only copy of the code which has the release version is the single bumpversion commit
# with the corresponding tag

if [ $do_release -eq 1 ]; then
    $base_cmd --message "Bump to next dev version: {current_version} --> {new_version}" patch
    echo "Bumped to new post-release dev version '$(<core/VERSION)'"
fi

# (5) all done, push and echo final message
echo "Pushing to git remote"
# git push && git push --tags

echo "Done bumping version, started at $vers_start, now at $(<core/VERSION)"
```

---

## Files to MODIFY

### 4. `core/__init__.py`

**Current content:**

```python
import sys

print(f"Initiating core module with Python version {sys.version}")
```

**Replace with** (adds VERSION read + `__version__` + version print, keeps the Python-version print):

```python
import sys
from pathlib import Path

# using versioning option 4 from https://packaging.python.org/en/latest/guides/single-sourcing-package-version/
version_file = Path(__file__).parent / "VERSION"
__version__ = version_file.read_text().strip()

print(f"Initiating core module with Python version {sys.version}")
print(f"traffic-data version = {__version__}")
```

> Use `print`, not `get_logger` — this matches the source template and the user's explicit choice.
> This file needs NO further change for the PEP 440 step (it reads whatever string is in `VERSION`).

### 5. `pyproject.toml`

Two edits:

1. Change the version line so the literal string matches `bumpversion.toml`'s `current_version`
   (required for bump-my-version's `search` to find it):
   ```toml
   version = "0.0.1-dev1"   # was: version = "0.0.1"
   ```
2. Add `bump-my-version` to the `ci` optional-dependencies group:
   ```toml
   ci = [
       "bump-my-version",
       "pre-commit",
       "pandas",  # only used by testing utils for fixed width txt file i/o
       "pytest",
       "ruff"
   ]
   ```

---

## ⚠️ Known risk (resolved by Step 7)

`0.0.1-dev1` is **not** PEP 440's canonical dev form (which is `0.0.1.dev1`); PEP 440 normalizes a
`-dev` separator to `.dev`. While the scheme is in the template-faithful `-dev1` form (Steps 1–6),
`uv`/build tooling may normalize or reject the `pyproject.toml` version string.

**Step 7 below converts the scheme to PEP 440**, which removes this risk entirely. If you are
executing the full plan in one pass, you may apply Step 7's values directly when creating the files
in Steps 1–5 (i.e. start at `0.0.1.dev1`) rather than creating the `-dev1` form and immediately
rewriting it. The two-phase layout here is for clarity; the end state is the PEP 440 form.

## Dependency note (repo security policy)

This change adds `bump-my-version` (from PyPI) to `pyproject.toml`'s `ci` extras. Per this repo's
security constraints, do not run ad-hoc `pip install`/`uv add`. The install happens when the user
(or the executing agent, if authorised) runs `uv sync --all-extras` — this is the expected,
explicitly-requested consequence of the feature, limited to this project's own `pyproject.toml`.

---

## Step 7 (final): Convert the scheme to PEP 440 conformance

PEP 440 uses a **dot** separator for the dev-release segment (`0.0.1.dev1`), not a dash. Apply the
following changes so the version strings are canonical PEP 440 and accepted cleanly by `uv`/build
tooling. The branch rules, dev/release workflow, and `bin/bump.sh` logic are unchanged — only the
separator and the literal version strings differ.

### 7a. `bumpversion.toml`

- Change the current version:
  ```toml
  current_version = "0.0.1.dev1"
  ```
- In the `parse` regex, change the pre-release **separator** from a dash to an escaped dot, and
  drop the dash from the label character class (it is no longer a valid separator):
  ```
      (?:
          \\.                           # dot separator for dev release segment (PEP 440)
          (?P<pre_l>[a-zA-Z]+)          # release label (str)
          (?P<pre_n>0|[1-9]\\d*)        # dev release number
      )?                                # dev release section is optional
  ```
- Change the dev `serialize` form to use a dot:
  ```toml
  serialize = [
      "{major}.{minor}.{patch}.{pre_l}{pre_n}",
      "{major}.{minor}.{patch}",
  ]
  ```
- The `[tool.bumpversion.parts.pre_l]` block (`values = ["dev", "final"]`, `optional_value = "final"`)
  and the `[[tool.bumpversion.files]]` entries are **unchanged**.

### 7b. `core/VERSION`

```
0.0.1.dev1
```

### 7c. `pyproject.toml`

```toml
version = "0.0.1.dev1"
```

### 7d. `bin/bump.sh` (cosmetic only)

No logic changes required — the script only reads/echoes the `core/VERSION` string. Optionally
update the comments that mention `1.2.3-dev1` / `-devX` to the dotted `1.2.3.dev1` form so the
documentation matches reality. This is non-functional.

After Step 7, the resulting versions are: dev → `0.0.1.dev1`, `0.0.1.dev2`, …; release → `0.0.1`,
followed immediately by `0.0.2.dev0`. These are all canonical PEP 440.

---

## Verification

Run from the repo root. **Bump steps create real commits and tags — run them on a throwaway
branch or be ready to reset** (`git reset --hard <pre-bump-sha>` and `git tag -d <tag>`).

1. **pyproject valid:** `uv sync --all-extras` succeeds with the PEP 440 `version = "0.0.1.dev1"`,
   and `bump-my-version` is installed (`uv run bump-my-version --help`).
2. **Version surfaced at import:** `python -c "import core; print(core.__version__)"` prints `0.0.1.dev1`.
   Also briefly run `python -m app.main` and confirm the `traffic-data version = 0.0.1.dev1` line prints at startup.
3. **Dev bump:** on a `dev` branch, `bash ./bin/bump.sh dev` (or `bash ./bin/bump.sh`) moves
   `0.0.1.dev1` → `0.0.1.dev2` in `core/VERSION` AND `pyproject.toml`, with a matching commit + tag.
4. **Release bump:** on `main`, `bash ./bin/bump.sh patch` produces clean `0.0.1` (tagged), then an
   immediate follow-up commit bumping to `0.0.2.dev0`. Verify both commits and the `0.0.1` tag exist.
5. **Branch guard:** from any branch that is not `main`/`dev`, `bash ./bin/bump.sh` exits non-zero
   with the "must be on 'main' or 'dev' to bump version" message.
6. **Tests unaffected:** `pytest` passes.

## Summary checklist

- [ ] Create `core/VERSION`
- [ ] Create `bumpversion.toml`
- [ ] Create `bin/bump.sh` + `chmod +x`
- [ ] Edit `core/__init__.py` (add `__version__` + print)
- [ ] Edit `pyproject.toml` (version field; add `bump-my-version` to `ci`)
- [ ] **Step 7:** convert the scheme to PEP 440 (`.dev` separator, `0.0.1.dev1`)
- [ ] Verify (steps 1–6 above)
