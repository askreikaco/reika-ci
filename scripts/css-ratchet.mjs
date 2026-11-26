#!/usr/bin/env node
// CSS ratchet: compare a BASE tree with a HEAD tree and fail only when a metric gets worse.
// Usage: node css-ratchet.mjs --base <dir> --head <dir> --glob '<glob>' [--bytes-slack 2048]
// Needs Node 22.22+ (stylelint 18 engines). Stylelint, fast-glob and @projectwallace/css-analyzer are resolved from
// CSS_GATE_TOOLS (a dir with node_modules), default: the current working directory.
import { createRequire } from 'node:module';
import { readFileSync, statSync, appendFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const CONFIG = path.resolve(here, '../configs/stylelint/reika.cjs');
const EXCEPTION_RE = /\/\*\s*stylelint-disable(?:-next-line|-line)?\s[^*]*\bdeclaration-no-important\b[^*]*\*\//g;
const IGNORE = ['**/node_modules/**', '**/*.min.css', '_base/**', '.css-gate-src/**', '.git/**'];

function parseArgs(argv) {
  const opts = { base: null, head: null, glob: null, bytesSlack: 2048 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      const v = argv[++i];
      if (v === undefined) throw new Error(`missing value for ${a}`);
      return v;
    };
    if (a === '--base') opts.base = next();
    else if (a === '--head') opts.head = next();
    else if (a === '--glob') opts.glob = next();
    else if (a === '--bytes-slack') opts.bytesSlack = Number(next());
    else throw new Error(`unknown argument: ${a}`);
  }
  if (!opts.base || !opts.head || !opts.glob) {
    throw new Error("usage: css-ratchet.mjs --base <dir> --head <dir> --glob '<glob>' [--bytes-slack N]");
  }
  if (!Number.isFinite(opts.bytesSlack) || opts.bytesSlack < 0) throw new Error('--bytes-slack must be >= 0');
  return opts;
}

const toolsDir = path.resolve(process.env.CSS_GATE_TOOLS || process.cwd());
const req = createRequire(path.join(toolsDir, 'package.json'));
const fg = req('fast-glob');
const stylelint = (await import(pathToFileURL(req.resolve('stylelint')).href)).default;
const analyzer = await import(pathToFileURL(req.resolve('@projectwallace/css-analyzer')).href);
const { declarations, selectors, specificity, stylesheet } = await import(
  pathToFileURL(req.resolve('@projectwallace/css-analyzer/collectors')).href
);

async function listFiles(root, glob) {
  const files = await fg(glob, { cwd: root, ignore: IGNORE, onlyFiles: true, dot: false });
  return files.sort();
}

async function lintTree(root, files) {
  const counts = {};
  if (files.length === 0) return counts;
  const abs = files.map((f) => path.join(root, f));
  const result = await stylelint.lint({ files: abs, configFile: CONFIG, cwd: root });
  for (const file of result.results) {
    for (const w of file.warnings) {
      counts[w.rule] = (counts[w.rule] || 0) + 1;
    }
  }
  return counts;
}

function analyzeTree(root, files) {
  const totals = { importants: 0, ids: 0, maxSpecificity: [0, 0, 0], bytes: 0, selectors: 0 };
  for (const f of files) {
    const css = readFileSync(path.join(root, f), 'utf8');
    totals.bytes += statSync(path.join(root, f)).size;
    const r = analyzer.analyze(css, {
      declarations: declarations(),
      selectors: selectors(),
      specificity: specificity(),
    });
    // !important lines covered by an exception comment do not count (see configs/stylelint/reika.cjs)
    const excepted = (css.match(EXCEPTION_RE) || []).length;
    totals.importants += Math.max(0, r.declarations.importants.total - excepted);
    totals.ids += r.selectors.ids.total;
    totals.selectors += r.selectors.total;
    for (const key of r.specificity.unique.keys()) {
      const s = key.split(',').map(Number);
      if (specNum(s) > specNum(totals.maxSpecificity)) totals.maxSpecificity = s;
    }
  }
  return totals;
}

const fmtSpec = (s) => s.join(',');
const specNum = (s) => s[0] * 1e6 + s[1] * 1e3 + s[2];

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const base = path.resolve(opts.base);
  const head = path.resolve(opts.head);
  const baseFiles = await listFiles(base, opts.glob);
  const headFiles = await listFiles(head, opts.glob);
  console.log(`files: base=${baseFiles.length} head=${headFiles.length} glob=${opts.glob}`);

  const baseLint = await lintTree(base, baseFiles);
  const headLint = await lintTree(head, headFiles);
  const baseAn = analyzeTree(base, baseFiles);
  const headAn = analyzeTree(head, headFiles);

  const rows = []; // {metric, base, head, fail}
  const rules = [...new Set([...Object.keys(baseLint), ...Object.keys(headLint)])].sort();
  for (const rule of rules) {
    const b = baseLint[rule] || 0;
    const h = headLint[rule] || 0;
    rows.push({ metric: `stylelint: ${rule}`, base: b, head: h, fail: h > b });
  }
  const add = (metric, b, h, fail) => rows.push({ metric, base: b, head: h, fail });
  add('!important (minus exceptions)', baseAn.importants, headAn.importants, headAn.importants > baseAn.importants);
  add('ID selectors', baseAn.ids, headAn.ids, headAn.ids > baseAn.ids);
  add('max specificity (info)', fmtSpec(baseAn.maxSpecificity), fmtSpec(headAn.maxSpecificity), false);
  add('selectors (info)', baseAn.selectors, headAn.selectors, false);
  const byteDelta = headAn.bytes - baseAn.bytes;
  add('bytes', baseAn.bytes, headAn.bytes, byteDelta > opts.bytesSlack);

  const lines = [
    '| metric | base | head | delta | status |',
    '|---|---:|---:|---:|---|',
  ];
  for (const r of rows) {
    const delta = typeof r.base === 'number' ? String(r.head - r.base) : '-';
    const status = r.fail ? 'FAIL' : 'ok';
    lines.push(`| ${r.metric} | ${r.base} | ${r.head} | ${delta} | ${status} |`);
  }
  if (rows.length === 0) lines.push('| (no violations, no metrics) | | | | ok |');
  lines.push('');
  lines.push(`bytes slack: ${opts.bytesSlack}`);
  const table = lines.join('\n');
  console.log(table);
  if (process.env.GITHUB_STEP_SUMMARY) {
    appendFileSync(process.env.GITHUB_STEP_SUMMARY, `## CSS ratchet\n\n${table}\n`);
  }

  const failed = rows.filter((r) => r.fail);
  if (failed.length) {
    for (const r of failed) console.error(`::error::ratchet failed: ${r.metric} ${r.base} -> ${r.head}`);
    process.exitCode = 1;
  } else {
    console.log('ratchet: ok');
  }
}

main().catch((e) => {
  console.error(e && e.stack ? e.stack : e);
  process.exitCode = 2;
});
