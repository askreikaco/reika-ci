# reika-ci

Shared CI building blocks: reusable GitHub Actions workflows, composite actions, test kit and configs.
A project keeps a short `ci.yml` and its own test map, and calls a pinned version of this repo.

## Layout
- `.github/workflows/` reusable workflows (`on: workflow_call`), grouped by prefix: `shared-*`, `node-*`, `wp-*`, `contract-*`.
- `actions/<stack>/<name>/action.yml` composite actions: `shared/`, `node/`, `wp/`.
- `packages/testkit/` browser test harness and shared checks (accessibility, touch targets, hidden controls, design tokens, hard-coded text, privacy probe, performance budget).
- `configs/` lint presets, PHPCS rules, Lighthouse budgets, axe rules, test-map JSON schema.
- `docs/` one page per stack and how to adopt.

## Principles
- Small change, small test: pull requests run the tests of the parts they touch plus a smoke set; core changes run everything; the full suite runs nightly.
- No secrets, hostnames, runner names or project details in this repository. Callers pass them as inputs or secrets.
- Callers pin a tag (`@v1`); Dependabot proposes updates.

## Gates
Ratchet gates for legacy repos: each gate compares the BASE ref with the HEAD and fails only when a metric gets worse. Existing debt does not turn CI red on day one; it can only shrink.

CSS (`css-gates.yml`): stylelint violations per rule (`configs/stylelint/reika.cjs`), `!important` count, ID selectors, total bytes (slack 2048 by default). Table goes to the job summary.
Also: `raw_color` / `raw_px` (raw colour literals and px in declarations, counted like ics.org.vn `code-debt-check`; border/shadow px and custom-property definitions are exempt), `token_dup_new` (a new literal custom property whose value repeats another literal token: fails; a pure `var(--x)` alias is never a duplicate) and `token_unused_new` (a new custom property with no `var(--name)` in css/js/php: warns, fails with `strict_tokens: true`). Consumers pass `token_glob` for their token file, where raw values are allowed.
```yaml
jobs:
  css:
    uses: askreikaco/reika-ci/.github/workflows/css-gates.yml@v1
    with:
      css_glob: 'css/**/*.css'
      # bytes_slack: 2048
      # runner: ubuntu-latest
```

PHP (`php-gates.yml`): `php -l` on changed `*.php` files (hard fail), then PHPCS with WordPress-Coding-Standards 3.4.1 on the same files as a ratchet (error count must not rise).
```yaml
jobs:
  php:
    uses: askreikaco/reika-ci/.github/workflows/php-gates.yml@v1
    with:
      php_paths: '.'
```

Rules of the ratchet: a metric passes when head <= base. Bytes pass when growth is within `bytes_slack`. Metrics marked info are printed and never fail.

Exceptions: put a reasoned disable on the line before a deliberate `!important` (or other rule):
```css
/* stylelint-disable-next-line declaration-no-important -- imp: <reason> */
```
Excepted `!important` lines are not counted. A disable without a `-- <reason>` part fails the stylelint gate.

Planned, not yet in this repo: Knip (dead code), Lighthouse CI (budgets), Playwright (browser tests).

## Use
```yaml
jobs:
  ci:
    uses: askreikaco/reika-ci/.github/workflows/node-app.yml@v1
    with:
      runs-on: ubuntu-latest
      test-map: tests/test-map.json
```

License: Apache-2.0.
