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
    # this should increment from .devX to final (no dev).
    # --allow-dirty as we still have the intermediate major/minor dev bump sitting in the working dir
    $base_cmd --allow-dirty --message "Release bump: $vers_start --> {new_version}" pre_l
    echo " ==== Release version is '$(<core/VERSION)' ==== "
fi

# (4) If Release, follow up with an immediate dev bump
# also want to immediately move to patch dev version so there is no lingering code that
# contains the clean release tag (1.2.3) but is actually the next dev version (1.2.4.dev0)
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
