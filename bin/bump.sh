#!/bin/bash

# Helper script using python package 'bump-my-version' with further constraints to
# allow for bumping project/package version number according to a set of rules
# see also https://pypi.org/project/bump-my-version/ and docs

# --- Script args ---
# call script either directly from repo root or any subdirectory
# ./bin/bump.sh [--dry-run] [--push] [ARG1]
# or with bash/source
# bash ./bin/bump.sh [--dry-run] [--push] [ARG1]
#
# Flags (must come before the version-part arg):
#   --dry-run   Preview the new version without writing files, committing, or tagging.
#               Note: for multi-step release paths (major/minor), only the first step
#               is previewed accurately since later steps compute from the unchanged file.
#   --push      Push commits and tags to the git remote after a successful bump.
#               Without this flag, commits/tags are created locally but not pushed.
#
# if provided, first positional argument (ARG1) will be used as version part to bump by,
# options: ['major', 'minor', 'patch', 'pre_n', 'dev']
# Arg can be left blank, in which case it defaults to 'dev'
# 'dev' is essentially an alias for 'pre_n', in that a dev bump will
# just increment the version number after the 'dev' suffix, e.g.
#   1.2.3.dev1  --> 1.2.3.dev2

# Context:
# A 'Dev' version number has the pattern with dev suffix: {major}.{minor}.{patch}.dev{pre_n}, e.g. 1.2.3.dev1
# A 'Release' version number has the 'clean' pattern:     {major}.{minor}.{patch},            e.g. 1.2.3

# Rules:
# - A bump from 'dev' branch will bump to a new .devX version number (same major/minor/patch)
# - A bump from 'main' branch will create a 'Release' version (just removes the .devX suffix
#   from the current major/minor/patch version number), followed immediately
#   by a patch bump to the next 'Dev' version
# - Bumping from any other branch will fail

# ================================== Script start ==================================
set -euo pipefail  # -e: exit on error, -u: error on unset vars, -o pipefail: fail on pipe errors

# --- Parse leading flags ---
DRY=0
DO_PUSH=0
while [[ "${1:-}" == --* ]]; do
    case "$1" in
        --dry-run) DRY=1; shift ;;
        --push)    DO_PUSH=1; shift ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done

# --- Change to repo root so all relative paths resolve regardless of caller's CWD ---
repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "Error: not inside a git repository" >&2
    exit 1
}
cd "$repo_root"

export BUMPVERSION_CONFIG_FILE='./bumpversion.toml'

# --- Check the tool is available ---
if ! command -v bump-my-version &>/dev/null; then
    echo "Error: 'bump-my-version' not found on PATH." >&2
    echo "Install the 'ci' extras and activate the venv:" >&2
    echo "  uv sync --extra ci && source .venv/bin/activate" >&2
    exit 1
fi

# (1) determine if we are on main or dev, and so whether to do a release or not
branch=$(git branch --show-current)

if [[ -z "$branch" ]]; then
    echo "Error: detached HEAD or no branch — must be on 'main' or 'dev' to bump version" >&2
    exit 1
elif [[ "$branch" == "main" ]]; then
    echo "Currently on main branch, bumping as release"
    do_release=1
elif [[ "$branch" == "dev" ]]; then
    echo "Currently on dev branch, bumping as development"
    do_release=0
else
    echo "Currently on branch '$branch', must be on 'main' or 'dev' to bump version"
    exit 1
fi


# (2) validate version argument
vers_arg="${1:-}"
vers_start=$(<core/VERSION)
echo "Starting at version $vers_start"

case "$vers_arg" in
    major|minor|patch|pre_n)
        echo "Will bump by '$vers_arg' version part"
        ;;
    pre_l)
        echo "Cannot bump by pre_level directly, this only used for a 'release' version from main"
        exit 1
        ;;
    dev)
        echo "Will bump by .devX version number only"
        vers_arg=pre_n
        ;;
    ?*)
        echo "Invalid version part to bump by: '$vers_arg'"
        exit 1
        ;;
    *)
        # if no arg, do same as 'pre_n', which is same as 'dev'
        echo "No version arg given, will bump by .devX version number only"
        vers_arg=pre_n
        ;;
esac

# (3) carry out bump version depending on inputs
base_cmd="bump-my-version bump"
if [[ "$DRY" -eq 1 ]]; then
    base_cmd="$base_cmd --dry-run --allow-dirty -v"
    echo "(dry-run: no files will be written, no commits or tags created)"
fi

if [[ "$do_release" -eq 0 ]]; then
    echo "Development version requested, just bumping by '$vers_arg' version part"
    $base_cmd --message "Dev bump: {current_version} --> {new_version}" "$vers_arg"

elif [[ "$do_release" -eq 1 ]]; then
    if [[ "$vers_arg" == "major" || "$vers_arg" == "minor" ]]; then
        echo "Intermediate '$vers_arg' bump as part of release"
        if [[ "$DRY" -eq 0 ]]; then
            # we don't commit or tag here as it's only an intermediate step
            $base_cmd --no-commit --no-tag "$vers_arg"
            echo "Bumped to intermediate $(<core/VERSION)"
        else
            $base_cmd "$vers_arg"
            echo "(dry-run: file unchanged; later release steps compute from current version)"
        fi
    elif [[ "$vers_arg" == "pre_n" ]]; then
        echo "Cannot bump by pre_number for a release version"
        exit 1
    else  # we don't actually increment patch version for a patch release, just bump pre_level (devX number)
        echo "Release version will have same maj.min.ptch number as starting dev version '$vers_start'"
    fi
    # then bump pre_l to create clean version - if $vers_arg was 'patch' this is all that's required
    echo "Bumping pre_level from dev to final (clean) for release"
    # this should increment from .devX to final (no dev).
    # --allow-dirty as we still have the intermediate major/minor dev bump sitting in the working dir
    $base_cmd --allow-dirty --message "Release bump: $vers_start --> {new_version}" pre_l
    if [[ "$DRY" -eq 0 ]]; then
        echo " ==== Release version is '$(<core/VERSION)' ==== "
    fi
fi

# (4) If Release (and not dry-run), follow up with an immediate dev bump
# also want to immediately move to patch dev version so there is no lingering code that
# contains the clean release tag (1.2.3) but is actually the next dev version (1.2.4.dev0)
# i.e. the only copy of the code which has the release version is the single bumpversion commit
# with the corresponding tag

if [[ "$do_release" -eq 1 && "$DRY" -eq 0 ]]; then
    $base_cmd --message "Bump to next dev version: {current_version} --> {new_version}" patch
    echo "Bumped to new post-release dev version '$(<core/VERSION)'"
fi

# (5) optionally push; echo final message
if [[ "$DRY" -eq 0 ]]; then
    if [[ "$DO_PUSH" -eq 1 ]]; then
        echo "Pushing commits and tags to git remote"
        git push && git push --tags
    else
        echo "Skipping push (pass --push to push commits + tags to remote)"
    fi
    echo "Done bumping version, started at $vers_start, now at $(<core/VERSION)"
else
    echo "(dry-run complete — no changes were made)"
fi
