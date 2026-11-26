#!/usr/bin/env node
// PHPCS (WordPress-Coding-Standards) ratchet on changed files: fail only when the error count rises.
// Usage: node php-ratchet.mjs --base <dir> --head <dir> --files <list.txt>
//   list.txt: one repo-relative *.php path per line (changed files, head side).
// Env: PHPCS_BIN (phpcs executable), PHPCS_INSTALLED_PATHS (comma-separated coding standard dirs).
import { readFileSync, existsSync, appendFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

function parseArgs(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i += 2) {
    const k = argv[i];
    const v = argv[i + 1];
    if (!k?.startsWith('--') || v === undefined) throw new Error(`bad argument near ${k}`);
    o[k.slice(2)] = v;
  }
  for (const k of ['base', 'head', 'files']) if (!o[k]) throw new Error(`missing --${k}`);
  return o;
}

function errorsFor(tree, files) {
  const existing = files.filter((f) => existsSync(path.join(tree, f)));
  const counts = new Map();
  if (existing.length === 0) return counts;
  const args = ['--runtime-set', 'installed_paths', process.env.PHPCS_INSTALLED_PATHS || '',
    '--standard=WordPress', '--report=json', '-q', ...existing];
  const r = spawnSync(process.env.PHPCS_BIN || 'phpcs', args, { cwd: tree, encoding: 'utf8', maxBuffer: 1 << 28 });
  let json;
  try {
    json = JSON.parse(r.stdout);
  } catch {
    throw new Error(`phpcs produced no JSON (exit ${r.status}): ${(r.stderr || '').slice(0, 500)}`);
  }
  for (const [abs, info] of Object.entries(json.files)) {
    counts.set(path.relative(tree, abs), info.errors);
  }
  return counts;
}

const opts = parseArgs(process.argv.slice(2));
const base = path.resolve(opts.base);
const head = path.resolve(opts.head);
const files = readFileSync(opts.files, 'utf8').split('\n').map((s) => s.trim()).filter((s) => s.endsWith('.php'));
const unique = [...new Set(files)];

if (unique.length === 0) {
  console.log('php ratchet: no changed PHP files');
  process.exit(0);
}

const b = errorsFor(base, unique);
const h = errorsFor(head, unique);
const sum = (m) => [...m.values()].reduce((a, n) => a + n, 0);
const bt = sum(b);
const ht = sum(h);

const rows = [];
for (const f of unique) {
  const be = b.get(f) || 0;
  const he = h.get(f) || 0;
  if (be !== 0 || he !== 0) rows.push({ f, be, he, fail: he > be });
}
const lines = [
  '| file | base errors | head errors | delta | status |',
  '|---|---:|---:|---:|---|',
  ...rows.map((r) => `| ${r.f} | ${r.be} | ${r.he} | ${r.he - r.be} | ${r.fail ? 'FAIL' : 'ok'} |`),
  `| **total** (${unique.length} changed file(s)) | ${bt} | ${ht} | ${ht - bt} | ${ht > bt ? 'FAIL' : 'ok'} |`,
  '',
];
const table = lines.join('\n');
console.log(table);
if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, `## PHPCS ratchet\n\n${table}\n`);

if (ht > bt) {
  console.error(`::error::phpcs errors rose from ${bt} to ${ht} on changed files`);
  process.exit(1);
}
console.log('php ratchet: ok');
