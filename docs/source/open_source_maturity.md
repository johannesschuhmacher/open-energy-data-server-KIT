# Open-Source Maturity Roadmap

This page captures the current implementation steps for improving OEDS as a
public open-source project, not only as an internally operable stack.

## Goals

- make every pull request pass a predictable baseline of checks
- reduce contributor setup friction
- provide reproducible onboarding examples
- separate reusable domain logic from UI and script entrypoints

## Implemented baseline

The repository now includes:

- GitHub workflows for CI checks and release tagging
- a manual release-tag workflow
- a root `.pre-commit-config.yaml`
- Dependabot updates for GitHub Actions, `uv`, Docker, and Compose
- a pull request template focused on validation and risk reporting

## What the workflows do

The GitHub workflows are the automated checks that run on pushes and pull
requests.

- `ci.yaml` runs three jobs:
  `lint`, `tests`, and `docs`
- `lint` runs `ruff` plus the configured `pre-commit` hooks on the maintained
  file set
- `tests` runs the Python unit-test suite under `tests/`
- `docs` builds the Sphinx docs in dummy mode so documentation regressions fail
  early
- `release.yaml` creates an annotated git tag when a maintainer enters a
  semantic version manually

These workflows make sure that the public branch is checked the same way every
time instead of relying on somebody remembering the right local commands.

## What "lint baseline" means

OEDS still contains older areas that are not yet uniformly formatted or linted.
The maintained lint baseline is the explicit subset of files that must already
be clean under `ruff` today.

That baseline currently covers:

- the new shared facades `crawler_core/` and `oeds_gapfill/`
- scheduler/admin runtime entry points
- the maintained gapfill scripts
- the focused tests that guard these public seams

The reason for a scoped baseline is pragmatic: contributors get predictable CI
checks immediately, while the remaining legacy files can be cleaned up
incrementally without blocking unrelated fixes.

## Contributor journey

The intended first-contribution path is:

1. follow [Getting Started](getting_started.md)
2. run [Local stack to first query](examples/local_stack_first_query.md)
3. pick a focused change and validate it with the commands in `CONTRIBUTING.md`
4. use the pull request template to document validation and risks

## Example-driven onboarding

The maintained walkthroughs are:

- [Local stack to first query](examples/local_stack_first_query.md)
- [First crawler change](examples/first_crawler_change.md)
- [Gapfill QA walkthrough](examples/gapfill_qa_walkthrough.md)

These are intentionally deterministic and avoid requiring access to external
production systems.

## Module boundary direction

OEDS is still one application repository, but the code should move toward
clearer internal seams.

### Stable facades introduced now

- `crawler_core`: shared runtime helpers and the crawler base class
- `oeds_gapfill`: reusable gapfill configuration, algorithms, and self-tests

These facades provide a stable import surface while the underlying files remain
in their current locations.

### Next target structure

```text
crawler/
  source-specific crawler modules

crawler_core/
  shared crawler base class
  database/runtime environment helpers
  metadata and logging helpers

oeds_gapfill/
  table/job config
  fill algorithms
  holdout and synthetic self-tests

crawler_runtime/
  scheduler-facing action execution
  locking
  run history

crawler_admin/
  FastAPI app
  HTML templates
  UI-specific view composition
```

## Recommended next refactors

1. move more non-UI imports in `crawler_admin/` behind `crawler_runtime`
2. stop importing reusable gapfill logic directly from `scripts/`
3. extract config parsing and validation into a dedicated internal package
4. package reusable components only after import boundaries are stable

## Good extraction examples

These are examples of changes that improve structure without forcing a
repository split too early.

- move `BaseCrawler`, schema creation, metadata updates, and runtime DB helpers
  behind `crawler_core`
- keep `crawler_admin.app` focused on HTTP and templates, while run history,
  lock handling, and action execution move toward `crawler_runtime`
- treat synthetic gapfill QA, holdout tests, and fill algorithms as reusable
  library behavior under `oeds_gapfill`, while `scripts/gapfill_timeseries.py`
  remains only a CLI entrypoint
- isolate YAML parsing, default merging, and validation into a config package so
  the admin UI and scheduler read the same rules from one place
