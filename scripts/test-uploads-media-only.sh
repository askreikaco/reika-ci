#!/usr/bin/env bash
# Self-test for uploads-media-only.sh: builds throwaway repos, expects pass/fail as labelled.
set -uo pipefail
GATE="$(cd "$(dirname "$0")" && pwd)/uploads-media-only.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mk() { # mk <name> ; creates repo with base commit containing uploads/a.css and src/x.php
  cd "$T" && rm -rf "$1" && mkdir "$1" && cd "$1" && git init -q && git config user.email t@t && git config user.name t
  mkdir -p uploads/ics-x src && echo '.a{}' > uploads/ics-x/a.css && echo '<?php' > src/x.php && echo '#' > uploads/ics-x/b.svg
  git add -A && git commit -qm base; }
run() { # run <expect 0|1> <label> <commands...>
  local want=$1 label=$2; shift 2; mk r; ( eval "$@" ) >/dev/null 2>&1
  git add -A && git commit -qm head >/dev/null 2>&1 || true
  bash "$GATE" HEAD~1 HEAD >/dev/null 2>&1; local got=$?
  [ "$got" = "$want" ] && echo "PASS $label" || { echo "FAIL $label (want $want got $got)"; exit 1; }
  cd "$T"; }
run 1 "add file under uploads"        "echo x > uploads/ics-x/new.jpg"
run 1 "modify css under uploads"      "echo '.b{}' >> uploads/ics-x/a.css"
run 1 "add nested uploads php"        "mkdir -p uploads/2026/11 && echo '<?php' > uploads/2026/11/s.php"
run 1 "type change under uploads"     "rm uploads/ics-x/b.svg && ln -s /etc/passwd uploads/ics-x/b.svg"
run 1 "move INTO uploads"             "git mv src/x.php uploads/ics-x/x.php"
run 0 "delete under uploads"          "git rm -q uploads/ics-x/a.css"
run 0 "move OUT of uploads"           "mkdir -p lib && git mv uploads/ics-x/a.css lib/a.css"
run 0 "change outside uploads"        "echo '.z{}' > src/y.css && echo 'x' >> src/x.php"
run 0 "uploads-like name, not dir"    "echo x > src/uploads-notes.md"
echo "all uploads-media-only self-tests passed"
