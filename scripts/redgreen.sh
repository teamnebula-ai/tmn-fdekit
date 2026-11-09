#!/usr/bin/env bash
# redgreen.sh — prove the new tests would have caught the bug.
#
#   redgreen.sh <base-ref> '<test command>'        e.g. redgreen.sh origin/main 'python3 -m pytest -q {tests}'
#
# 1. RED:   check out <base-ref> in a throwaway worktree, copy in ONLY the test files
#           this branch added or changed, run the command. It must FAIL: the old code
#           should not satisfy the new tests.
# 2. GREEN: run the same command on the current tree. It must PASS.
#
# `{tests}` in the command is replaced by the changed test files, so only they run.
# Dependency dirs (node_modules, .venv, venv) are symlinked into the worktree so a
# red result means "old code fails the test", not "packages missing". Still read
# the red output: a failure for the wrong reason (import error, missing fixture)
# proves nothing, and the script prints its tail so you can tell.
#
# Exit 0 = red then green (the tests prove the change). 1 = they don't. 2 = usage.
set -uo pipefail

base="${1:-}"; cmd="${2:-}"
if [[ -z "$base" || -z "$cmd" ]]; then
  echo "usage: redgreen.sh <base-ref> '<test command, may use {tests}>'" >&2; exit 2
fi
root="$(git rev-parse --show-toplevel)" || exit 2
cd "$root" || exit 2
git rev-parse --verify -q "$base" >/dev/null || { echo "unknown ref: $base" >&2; exit 2; }

test_re="${TMN_FDEKIT_TEST_RE:-(^|/)(tests?|__tests__|spec)/|(\.|_)(test|spec)\.[a-z]+$|^test_[^/]*\.py$|/test_[^/]*\.py$|_test\.go$}"
tests=()
while IFS= read -r f; do
  [[ -n "$f" && -f "$f" ]] && tests+=("$f")
done < <( { git diff --name-only --diff-filter=AM "$base"...HEAD; git diff --name-only --diff-filter=AM HEAD; git ls-files --others --exclude-standard; } | sort -u | grep -E "$test_re" | grep -Ev '(^|/)(__pycache__|node_modules|\.pytest_cache|dist|build)/|\.(pyc|pyo|class|o)$' )

if [[ ${#tests[@]} -eq 0 ]]; then
  echo "NO TESTS CHANGED since $base. Nothing proves this change; add a test that fails without it." ; exit 1
fi
joined="$(printf '%q ' "${tests[@]}")"
run_cmd="${cmd//\{tests\}/$joined}"

wt="$(mktemp -d "${TMPDIR:-/tmp}/redgreen.XXXXXX")"
cleanup() { git worktree remove --force "$wt" >/dev/null 2>&1; rm -rf "$wt"; }
trap cleanup EXIT INT TERM
git worktree add -q --detach "$wt" "$base" || exit 2
for f in "${tests[@]}"; do mkdir -p "$wt/$(dirname "$f")"; cp "$f" "$wt/$f"; done
for d in node_modules .venv venv; do [[ -e "$root/$d" && ! -e "$wt/$d" ]] && ln -s "$root/$d" "$wt/$d"; done

export PYTHONDONTWRITEBYTECODE=1   # stale bytecode must never decide red or green
find "$wt" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
log="$(mktemp "${TMPDIR:-/tmp}/redgreen-log.XXXXXX")"
echo "tests: ${tests[*]}"
( cd "$wt" && eval "$run_cmd" ) >"$log" 2>&1; red=$?
if [[ $red -eq 0 ]]; then
  echo "RED    FAIL  the new tests PASS on $base too, so they do not detect this change."
  tail -n 15 "$log" | sed 's/^/       /'; rm -f "$log"; exit 1
fi
echo "RED    ok    tests fail on $base (exit $red). Check it fails for the right reason:"
tail -n 12 "$log" | sed 's/^/       /'
if grep -Eq "ImportError|ModuleNotFoundError|AttributeError: module|NameError|cannot import name|Cannot find module|is not a function|is not defined|undefined: " "$log"; then
  echo "NOTE   red only because the code under test is new on this branch. That proves the tests run, not that"
  echo "       they catch bugs. Break the new code once (drop a check, skip a write) and confirm a test fails."
fi

( eval "$run_cmd" ) >"$log" 2>&1; green=$?
if [[ $green -ne 0 ]]; then
  echo "GREEN  FAIL  tests fail on the current tree (exit $green):"
  tail -n 20 "$log" | sed 's/^/       /'; rm -f "$log"; exit 1
fi
echo "GREEN  ok    tests pass on the current tree."
rm -f "$log"
echo "REDGREEN PASS"
