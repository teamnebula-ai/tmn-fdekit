#!/usr/bin/env bash
set -eu
git clone -q "$(dirname "$0")/files/repo.bundle" repo
cd repo
git branch -q main origin/main 2>/dev/null || true
git checkout -q feat/ORD-7-cancel
