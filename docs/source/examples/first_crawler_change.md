# First Crawler Change

This walkthrough shows the smallest reviewable code change that touches the
real OEDS development loop.

## Goal

Modify one crawler, validate it locally, and document the change in the same
pull request.

## Suggested first change

Pick one of these small changes:

- clarify a crawler log message
- tighten config validation for one crawler-specific option
- add one missing documentation note for an authenticated source

## Steps

1. Read the crawler implementation and its docs page:

   - `crawler/<crawler_name>.py`
   - `docs/source/crawlers/<crawler_name>.md`

2. Update the crawler code.

3. If the change affects configuration behavior, update `CRAWLER_CONFIG.yml`
   examples or docs.

4. Run focused validation:

   ```bash
   uv run --only-group dev ruff check
   uv run --only-group dev ruff format --check
   uv run --with pytest python -m pytest tests
   ```

5. Build the docs if you touched documentation:

   ```bash
   uv run --only-group docs sphinx-build -b dummy docs/source docs/_build/dummy
   ```

## Pull request checklist

- explain the problem before the implementation detail
- include the exact commands you ran
- note any crawler credentials or source access assumptions that reviewers need

## Why this example matters

It forces code, configuration, docs, and validation to stay aligned. That is
the baseline behavior external contributors expect from a healthy OSS project.
