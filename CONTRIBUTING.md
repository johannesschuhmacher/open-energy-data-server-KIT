# Contributing

Thank you for contributing to OEDS.

## Before you start

For local setup and service overview, use:

- [README.md](README.md)
- [docs/source/getting_started.md](docs/source/getting_started.md)
- [docs/source/deployment.md](docs/source/deployment.md)

## Development expectations

When you add or change a crawler:

1. update the crawler code under `crawler/`
2. register or adjust its entry in `CRAWLER_CONFIG.yml`
3. document it under `docs/source/crawlers/`
4. document authentication, source license, and downstream dependencies
5. add required bootstrap SQL to `init.sql` if fresh installs need it
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

- `uv run --only-group dev ruff check`
- `uv run --only-group dev ruff format --check`
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

Small, reviewable changes are preferred over large mixed refactors.
