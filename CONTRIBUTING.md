# Contributing
- One change per pull request; describe what it does and how it was tested.
- Reusable workflows go in `.github/workflows/` (prefix `shared-`, `node-`, `wp-` or `contract-`); composite actions in `actions/<stack>/<name>/`.
- Inputs over hard-coded values: no secrets, hostnames, runner labels or project names in this repository.
- Every workflow and action needs a self-test in `.github/workflows/selftest-*.yml`.
- Breaking changes need a new major tag.
