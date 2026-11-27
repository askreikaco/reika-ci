#!/usr/bin/env bash
# reika-ci gate: uploads/ is media-only (owner 2026-11-27, "better block uploads for good").
# Fails the PR if it ADDS, MODIFIES, copies or changes the type of ANY file under an uploads/ path
# (any file type). Deleting files and moving them OUT of uploads/ are allowed (ratchet down).
# Usage: uploads-media-only.sh <base-sha> <head-sha>   (run inside the caller repo checkout)
set -euo pipefail
BASE="${1:?base sha}"; HEAD="${2:?head sha}"
# --no-renames: a rename INTO uploads/ shows as A (blocked); a rename OUT shows as D (allowed).
BAD=$(git diff --no-renames --name-status "$BASE" "$HEAD" | awk -F'\t' '$1 ~ /^[ACMT]/ {print $2}' \
  | grep -E '(^|/)uploads/' || true)
if [ -n "$BAD" ]; then
  echo "::error::uploads/ is media-only. This PR adds or modifies files under uploads/:"
  echo "$BAD" | sed 's/^/  - /'
  echo "Media goes in via WordPress (WP MCP or wp media import). CSS/JS/code/backups/data never go in uploads/. CSS: theme repo components by PR."
  exit 1
fi
echo "uploads/ gate ok: no added or modified files under uploads/."
