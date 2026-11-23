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
