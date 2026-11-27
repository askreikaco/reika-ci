#!/usr/bin/env node
// CSS ratchet: compare a BASE tree with a HEAD tree and fail only when a metric gets worse.
// Usage: node css-ratchet.mjs --base <dir> --head <dir> --glob '<glob>' [--bytes-slack 2048]
//        [--token-glob '<glob>'] [--strict-tokens]
// Needs Node 22.22+ (stylelint 18 engines). Stylelint, fast-glob and @projectwallace/css-analyzer are resolved from
// CSS_GATE_TOOLS (a dir with node_modules), default: the current working directory.
// Raw-value metrics (raw_color, raw_px) follow ics.org.vn bin/code-debt-check (css_color, css_px); see README "CSS gates".
import { createRequire } from 'node:module';
import { readFileSync, statSync, appendFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const CONFIG = path.resolve(here, '../configs/stylelint/reika.cjs');
const EXCEPTION_RE = /\/\*\s*stylelint-disable(?:-next-line|-line)?\s[^*]*\bdeclaration-no-important\b[^*]*\*\//g;
const IGNORE = ['**/node_modules/**', '**/*.min.css', '_base/**', '.css-gate-src/**', '.git/**'];

// CSS named colours (CSS Color 4). transparent, currentcolor, inherit, initial and unset are not colours here.
const NAMED_COLORS = `aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet
brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan
darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred
darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue
dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green
greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon
lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta
maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen
mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab
orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum
powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna
silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet
wheat white whitesmoke yellow yellowgreen`.split(/\s+/);
const NAMED_RE = new RegExp(`(?<![\\w.#-])(${NAMED_COLORS.join('|')})(?![\\w-])`, 'gi');
const HEX_RE = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])/g;
const FN_COLOR_RE = /\b(?:rgba?|hsla?)\(/gi;
const PX_RE = /(?<![\w.])([+-]?(?:\d+\.?\d*|\.\d+))px\b/g;

function parseArgs(argv) {
  const opts = { base: null, head: null, glob: null, bytesSlack: 2048, tokenGlob: '', strictTokens: false };
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
    else if (a === '--token-glob') opts.tokenGlob = next();
    else if (a === '--strict-tokens') opts.strictTokens = true;
    else throw new Error(`unknown argument: ${a}`);
  }
  if (!opts.base || !opts.head || !opts.glob) {
    throw new Error("usage: css-ratchet.mjs --base <dir> --head <dir> --glob '<glob>' [--bytes-slack N] [--token-glob '<glob>'] [--strict-tokens]");
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
  if (!glob) return [];
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

// ---- raw values (raw_color, raw_px) and design tokens (token_dup_new, token_unused_new) ----

const readText = (root, f) => readFileSync(path.join(root, f), 'utf8');
const blank = (s) => s.replace(/[^\n]/g, ' ');

// Blank comments; blank strings unless keepStrings (token values need their strings: "Inter" != "Roboto").
function stripCss(src, keepStrings) {
  let out = '';
  let i = 0;
  const n = src.length;
  while (i < n) {
    const c = src[i];
    if (c === '/' && src[i + 1] === '*') {
      let e = src.indexOf('*/', i + 2);
      e = e < 0 ? n : e + 2;
      out += blank(src.slice(i, e));
      i = e;
      continue;
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n && src[j] !== c && src[j] !== '\n') {
        if (src[j] === '\\') j++;
        j++;
      }
      const e = Math.min(j + 1, n);
      out += keepStrings ? src.slice(i, e) : blank(src.slice(i, e));
      i = e;
      continue;
    }
    out += c;
    i++;
  }
  return out;
}

// Split into {text, term}; term '{' = selector or at-rule prelude, ';' or '}' = declaration.
function cssSegments(code) {
  const segs = [];
  let start = 0;
  for (let i = 0; i < code.length; i++) {
    const c = code[i];
    if (c === '{' || c === ';' || c === '}') {
      segs.push({ text: code.slice(start, i).trim(), term: c });
      start = i + 1;
    }
  }
  return segs;
}

// Declarations {prop, value}. Prop keeps its case (custom properties are case-sensitive).
// Skips at-rules and selectors, so @media/@container params are never declarations.
function cssDeclarations(src, { keepStrings = false, keepUrl = false } = {}) {
  const out = [];
  for (const s of cssSegments(stripCss(src, keepStrings))) {
    if (s.term === '{' || !s.text || s.text.startsWith('@')) continue;
    const colon = s.text.indexOf(':');
    if (colon < 0) continue;
    let value = s.text.slice(colon + 1);
    if (!keepUrl) value = value.replace(/url\([^)]*\)/gi, ' ');
    out.push({ prop: s.text.slice(0, colon).trim(), value: value.trim() });
  }
  return out;
}

const countMatches = (s, re) => [...s.matchAll(re)].length;

// Raw px exemptions: border*-width and box/text-shadow (ratchet only; code-debt-check counts them).
const pxExemptProp = (p) => /^border[\w-]*-width$/.test(p) || /(^|-)(box|text)-shadow$/.test(p);

// token-glob files are the token layer, so raw values there are allowed.
async function tokenExemptSet(root, tokenGlob) {
  return new Set(await listFiles(root, tokenGlob));
}

function analyzeRaw(root, files, exempt, hasTokenGlob) {
  const t = { color: 0, px: 0 };
  for (const f of files) {
    if (exempt.has(f)) continue;
    for (const d of cssDeclarations(readText(root, f))) {
      // Without --token-glob, custom-property definitions are exempt everywhere (legacy behaviour).
      // With it, they are exempt only inside token files (exempt set); elsewhere their raw values count.
      if (d.prop.startsWith('--') && !hasTokenGlob) continue;
      const prop = d.prop.toLowerCase();
      t.color += countMatches(d.value, HEX_RE) + countMatches(d.value, FN_COLOR_RE);
      if (!/^font(-family)?$/.test(prop)) t.color += countMatches(d.value, NAMED_RE);
      if (pxExemptProp(prop)) continue;
      for (const m of d.value.matchAll(PX_RE)) {
        const v = Math.abs(parseFloat(m[1]));
        if (v !== 0 && v !== 1 && v !== 2) t.px++;
      }
    }
  }
  return t;
}

// Token normalisation: case, whitespace, #abc == #aabbcc, #ffffffff == #fff, rgb()/rgba() with alpha 1 == hex.
function normToken(v) {
  let s = v.replace(/\s+/g, ' ').trim().toLowerCase();
  s = s.replace(/#([0-9a-f]+)(?![\w-])/g, (m, h) => {
    if (![3, 4, 6, 8].includes(h.length)) return m;
    let e = h.length <= 4 ? h.split('').map((c) => c + c).join('') : h;
    if (e.length === 8 && e.endsWith('ff')) e = e.slice(0, 6);
    return `#${e}`;
  });
  s = s.replace(/\b(rgba?)\(([^()]*)\)/g, (m, fn, inner) => {
    const p = inner.split(/[\s,/]+/).filter(Boolean);
    if (p.length < 3 || p.length > 4) return m;
    const rgb = p.slice(0, 3);
    if (!rgb.every((x) => /^\d+(\.\d+)?$/.test(x))) return m;
    const a = p[3] === undefined ? 1 : p[3].endsWith('%') ? parseFloat(p[3]) / 100 : parseFloat(p[3]);
    if (a >= 1) return `#${rgb.map((x) => Math.round(Number(x)).toString(16).padStart(2, '0')).join('')}`;
    return `${fn}(${rgb.map((x) => Number(x)).join(',')},${a})`;
  });
  return s.replace(/\s*([,/()])\s*/g, '$1');
}

// Custom-property definitions: name -> {value, file}. First definition wins (dark-mode repeats share the name).
function tokenDefs(root, cssFiles) {
  const defs = new Map();
  for (const f of cssFiles) {
    for (const d of cssDeclarations(readText(root, f), { keepStrings: true, keepUrl: true })) {
      if (d.prop.startsWith('--') && !defs.has(d.prop)) defs.set(d.prop, { value: d.value, file: f });
    }
  }
  return defs;
}

// A pure alias is var(--other) and holds no value of its own: a semantic token pointing at a primitive is not a duplicate.
const isPureAlias = (value) => /^var\(\s*--[\w-]+\s*\)$/.test(value.trim());

// New literal tokens whose normalised value equals another literal token's value in HEAD (each new literal counts once).
// Only literal definitions are holders; a new alias is never a duplicate.
function duplicateNewTokens(headDefs, newNames) {
  const byValue = new Map();
  for (const [name, def] of headDefs) {
    if (isPureAlias(def.value)) continue;
    const k = normToken(def.value);
    if (!byValue.has(k)) byValue.set(k, []);
    byValue.get(k).push(name);
  }
  return newNames.filter((name) => {
    const def = headDefs.get(name);
    if (isPureAlias(def.value)) return false;
    return byValue.get(normToken(def.value)).length > 1;
  });
}

// Every var(--name) reference in the tree (css, js, php). Raw text: a reference in a comment still counts.
function tokenRefs(root, files) {
  const refs = new Set();
  for (const f of files) {
    for (const m of readText(root, f).matchAll(/var\(\s*(--[\w-]+)/g)) refs.add(m[1]);
  }
  return refs;
}

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

  const baseExempt = await tokenExemptSet(base, opts.tokenGlob);
  const headExempt = await tokenExemptSet(head, opts.tokenGlob);
  const hasTokenGlob = Boolean(opts.tokenGlob);
  if (!hasTokenGlob) console.log('raw_*: custom properties exempt everywhere (no --token-glob)');
  const baseRaw = analyzeRaw(base, baseFiles, baseExempt, hasTokenGlob);
  const headRaw = analyzeRaw(head, headFiles, headExempt, hasTokenGlob);

  // Token metrics scan the whole tree: token files are rarely inside --glob, and usage can be in js/php.
  const baseCss = await listFiles(base, '**/*.css');
  const headAll = await listFiles(head, '**/*.{css,js,php}');
  const headCss = headAll.filter((f) => f.endsWith('.css'));
  const baseDefs = tokenDefs(base, baseCss);
  const headDefs = tokenDefs(head, headCss);
  const newNames = [...headDefs.keys()].filter((n) => !baseDefs.has(n));
  const dupNew = duplicateNewTokens(headDefs, newNames);
  const refs = tokenRefs(head, headAll);
  const unusedNew = newNames.filter((n) => !refs.has(n));

  const rows = []; // {metric, base, head, fail, warn}
  const rules = [...new Set([...Object.keys(baseLint), ...Object.keys(headLint)])].sort();
  for (const rule of rules) {
    const b = baseLint[rule] || 0;
    const h = headLint[rule] || 0;
    rows.push({ metric: `stylelint: ${rule}`, base: b, head: h, fail: h > b });
  }
  const add = (metric, b, h, fail, warn = false) => rows.push({ metric, base: b, head: h, fail, warn });
  add('!important (minus exceptions)', baseAn.importants, headAn.importants, headAn.importants > baseAn.importants);
  add('ID selectors', baseAn.ids, headAn.ids, headAn.ids > baseAn.ids);
  add('max specificity (info)', fmtSpec(baseAn.maxSpecificity), fmtSpec(headAn.maxSpecificity), false);
  add('selectors (info)', baseAn.selectors, headAn.selectors, false);
  const byteDelta = headAn.bytes - baseAn.bytes;
  add('bytes', baseAn.bytes, headAn.bytes, byteDelta > opts.bytesSlack);
  add('raw_color', baseRaw.color, headRaw.color, headRaw.color > baseRaw.color);
  add('raw_px', baseRaw.px, headRaw.px, headRaw.px > baseRaw.px);
  // Base is 0 by construction: the new-token set is taken against BASE, so any new duplicate fails.
  add('token_dup_new', 0, dupNew.length, dupNew.length > 0);
  // Warn-only unless --strict-tokens: Bricks content can reference tokens that CI cannot see.
  add('token_unused_new', 0, unusedNew.length, opts.strictTokens && unusedNew.length > 0, !opts.strictTokens);

  const lines = [
    '| metric | base | head | delta | status |',
    '|---|---:|---:|---:|---|',
  ];
  const statusOf = (r) => {
    if (r.fail) return 'FAIL';
    if (r.warn && r.head > r.base) return 'warn';
    return 'ok';
  };
  for (const r of rows) {
    const delta = typeof r.base === 'number' ? String(r.head - r.base) : '-';
    lines.push(`| ${r.metric} | ${r.base} | ${r.head} | ${delta} | ${statusOf(r)} |`);
  }
  if (rows.length === 0) lines.push('| (no violations, no metrics) | | | | ok |');
  lines.push('');
  lines.push(`bytes slack: ${opts.bytesSlack}`);
  lines.push(`token glob: ${opts.tokenGlob || '(none)'}; strict tokens: ${opts.strictTokens}`);
  const table = lines.join('\n');
  console.log(table);
  if (dupNew.length) console.log(`new duplicate tokens: ${dupNew.join(', ')}`);
  if (unusedNew.length) console.log(`new unused tokens: ${unusedNew.join(', ')}`);
  if (process.env.GITHUB_STEP_SUMMARY) {
    appendFileSync(process.env.GITHUB_STEP_SUMMARY, `## CSS ratchet\n\n${table}\n`);
  }

  const failed = rows.filter((r) => r.fail);
  for (const r of rows.filter((x) => x.warn && !x.fail && x.head > x.base)) {
    console.log(`::warning::ratchet warn: ${r.metric} ${r.base} -> ${r.head}`);
  }
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
