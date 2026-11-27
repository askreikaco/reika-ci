#!/usr/bin/env bash
# Self-test for css-ratchet.mjs metrics raw_color, raw_px, token_dup_new, token_unused_new.
# Needs CSS_GATE_TOOLS (dir with node_modules: stylelint, fast-glob, @projectwallace/css-analyzer).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$ROOT/scripts/css-ratchet.mjs"
FX="$ROOT/tests/fixtures/css-ratchet"

# run <want-exit> <label> <base-fixture> <head-fixture> [extra gate args...]
run() {
  local want=$1 label=$2 base=$3 head=$4
  shift 4
  local out got
  out=$(node "$GATE" --base "$FX/$base" --head "$FX/$head" --glob '**/*.css' "$@" 2>&1)
  got=$?
  if [ "$got" = "$want" ]; then
    echo "PASS $label (exit $got)"
  else
    echo "FAIL $label (want exit $want, got $got)"
    echo "$out"
    exit 1
  fi
}

# raw_color
run 1 "raw_color worse fails"                 base color-bad
run 0 "raw_color equal passes"                base color-ok
run 0 "raw_color better passes"               base color-better
run 1 "raw_color token-glob off: raw file fails" base tokens-raw
run 0 "raw_color token-glob exempts token file" base tokens-raw --token-glob 'tokens/**'
run 0 "custom property with raw colour is exempt" base custom-prop

# raw_px
run 1 "raw_px worse fails"                    base px-bad
run 0 "raw_px exempt: border width, shadow, @media, 0/1/2px" base px-ok

# token_dup_new (base has pre-existing duplicates; only new ones count)
run 0 "token dup: unchanged duplicates pass"  dup-base dup-base
run 1 "token dup: new duplicates fail"        dup-base dup-bad

# token_unused_new (warn by default, fail with --strict-tokens)
run 0 "token unused new: warn only"           base unused
run 1 "token unused new: strict fails"        base unused --strict-tokens
run 0 "token used new: strict passes"         base used --strict-tokens

echo "all css-ratchet metric self-tests passed"
