# Offline CSS verify harness

Purpose: shift-free CSS refactor verify. Renders captured pages offline with
the base CSS (A) and the candidate CSS (F), then compares computed styles per
element. Control A vs A must give 0 shifted elements before any result counts.

## Layout
- Data root = `HARNESS_ROOT` (default: the old scratchpad path). Not in git.
- Expected under the root: `bulk2/har/*.html|*.har` (captures), `bulk2/masks.json`,
  `layer/variants/A_css.json`, `layer/conf/pages_torn.txt`, `layer/` scripts dir.
- Scripts here are flat; `conf/` and `capture/` are subdirs.
- Variants: `A_css.json` (live minified base), `F_css.json` (candidate, from prep_fix.py).
- Pages list: `pages.txt` (one URL per line; passed as `PAGES`).
- Masks: `masks.json` (`[[url, prop], ...]`, passed as `MASKS`).

## Workflow (in order)
1. Capture HARs once per page at 1440: `capture/record.py` (writes `bulk2/har/`).
2. Build A from live: minify live theme CSS with the same minifier as the droplet
   (lightningcss), write `A_css.json`.
3. Build F: `python3 prep_fix.py <repo> <outdir>` writes `<outdir>/F_css.json`
   (optional 3rd arg: strip file, adds `--ics-strip:<id>` markers).
4. Measure:
   `TAG=<name> VARDIR=<dir> BASE_SPEC=raw:A TEST_SPEC=raw:F MASKS=<masks.json> python3 measure_layer3.py 1440,768,390`
5. Results in `res/<TAG>`. Read the shifted counts; 0 = pass.
6. Attribution / bisect: `strip_one.py <F_css.json> <file_substr> <outdir> [ids|ALL]`,
   then `bisect_one.py <ids_file> <tag_prefix> [pages_file] [max_tests] [widths]`.

## Specs (BASE_SPEC / TEST_SPEC)
- `raw:A` / `raw:F`: captured HTML with CSS replaced by the variant.
- `L:A`, `L:B`: layered HTML mode (`layer_html.py`, cascade layer wrap).
- `L2:F`, `L2:B`: second layered mode (`layer_html2.py`), used by bisect_one.py.
- Aggregate outputs with `conf/collect2.py` (writes `layer/conf/<OUT>`) and `conf/agg2.py`.

## Rules
- One run at a time: check `pgrep -fa measure_layer3` first.
- CONC 4 max (OOM). Harness browsers share the container limit.
- Use `nohup ... &`; re-running resumes and skips finished files. Delete stale partial results first.
- Known flake: header>section:1>div:1 auto margin. Confirm it is not a real shift before reporting.
- Breakpoint moves: run bracket widths (old-1, old, old+1, new-1, new, new+1), not only 1440/768/390.
- `dead per CDP` is a hypothesis. Verify each deletion on all pages (2026-11-28: 3 of 6 were live elsewhere).
- Never run a live per-rule loop (about 24 s per rule); use offline runs.

## Data
- HARs and masks are NOT in git (size). Store them in Drive (owner) and set
  `HARNESS_ROOT` to the local copy.
- No credentials in these scripts. Do not add any.

Source of method: reika-ai `shared/wordpress/css-cleanup-research.md` ("## Method").
