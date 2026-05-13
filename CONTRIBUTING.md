# Contributing

Thank you for contributing to OEDS.

## Before you start

For local setup and service overview, use:

- [README.md](README.md)
- [docs/source/getting_started.md](docs/source/getting_started.md)
- [docs/source/deployment.md](docs/source/deployment.md)
- [docs/source/examples/local_stack_first_query.md](docs/source/examples/local_stack_first_query.md)

## Local contributor workflow

Set up the repository root once:

```bash
uv sync --locked
uv tool run pre-commit install
```

Recommended first-pass validation before opening a pull request:

```bash
uv run --with pytest python -m pytest tests
uv run --only-group docs sphinx-build -b dummy docs/source docs/_build/dummy
uv tool run pre-commit run --all-files
```

Current maintained lint scope:

```bash
uv run --only-group dev ruff check crawler_admin/gapfill_service.py crawler_admin/runtime_service.py crawler_admin_server.py crawler_core crawler_scheduler.py oeds_gapfill scripts/gapfill_timeseries.py scripts/refresh_entsoe_availability_map.py tests/test_gapfill_config.py tests/test_gapfiller_core.py tests/test_public_facades.py tests/test_runtime_env.py
uv run --only-group dev ruff format --check crawler_admin/gapfill_service.py crawler_admin/runtime_service.py crawler_admin_server.py crawler_core crawler_scheduler.py oeds_gapfill scripts/gapfill_timeseries.py scripts/refresh_entsoe_availability_map.py tests/test_gapfill_config.py tests/test_gapfiller_core.py tests/test_public_facades.py tests/test_runtime_env.py
```

This scoped lint list is the current lint baseline. In practice that means:
every pull request must keep these maintained paths clean under `ruff`, while
older untouched areas are cleaned up gradually instead of forcing a full-repo
lint migration in one step.

If one of these commands is not relevant for your change, note that explicitly
in the pull request.

## Development expectations

When you add or change a crawler:

1. update the crawler code under `crawler/`
2. register or adjust its entry in `CRAWLER_CONFIG.yml`
3. document it under `docs/source/crawlers/`
4. document authentication, source license, and downstream dependencies
5. add required bootstrap SQL to `docker/initdb/10-init.sql` if fresh installs need it
6. verify the relevant dashboards, scripts, or downstream views

## Documentation

This repository uses Sphinx to build the published documentation from
`docs/source/`.

Useful local build command:

```bash
uv run --only-group docs python -m sphinx -E -a -b html docs/source docs/_build/html
```

Each regularly used crawler should have its own page in
`docs/source/crawlers/` following the shared section order documented in
`docs/source/crawlers/README.md`.

## Checks

Run the checks that match your change. Typical examples:

- `uv run --only-group dev ruff check <maintained-paths>`
- `uv run --only-group dev ruff format --check <maintained-paths>`
- `uv run --with pytest python -m pytest tests`
- `uv tool run pre-commit run --all-files`
- targeted Python syntax checks with `python -m py_compile ...`
- crawler-specific manual test runs
- SQL validation against a local database
- Sphinx documentation build

If a check could not be run, note that clearly in your change description.

## Secrets and sensitive data

- do not commit `.env` files, credentials, or tokens
- do not hardcode source-system credentials into crawler modules
- do not paste internal-only deployment commands into the public docs

If you find a security issue, follow [SECURITY.md](SECURITY.md).

## Pull requests

A good contribution usually includes:

- a short problem statement
- the implemented change
- validation performed
- follow-up risks or limitations

Use the pull request template in `.github/pull_request_template.md` and keep
the validation section concrete. If a change touches operator workflow, source
licensing assumptions, or deployment defaults, call that out explicitly.

Small, reviewable changes are preferred over large mixed refactors.
