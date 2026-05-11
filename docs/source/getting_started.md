# Getting Started

This guide covers the local development setup, crawler execution, and the main
services that ship with OEDS.

## Requirements

For the local stack:

- Docker with the Compose plugin, or a compatible Podman setup

For crawler execution:

- `uv`

## Start the local services

From the repository root:

```bash
docker compose up -d
```

If you already have a populated PostgreSQL/TimescaleDB data directory from an
older major version, do not treat this as an in-place image swap. Moving to
PostgreSQL 18 requires a database migration such as `pg_upgrade` or
dump/restore.

This starts the standard local stack:

- PostgreSQL / TimescaleDB on `localhost:6432`
- PgAdmin on `http://localhost:8080/`
- PostgREST on `http://localhost:3001/`
- Grafana on `http://localhost:3006/`

If a port is already used locally, override it before starting Compose, for
example `OEDS_POSTGRES_PORT=16432 docker compose up -d`.

Optional crawler services are available through the `crawlers` profile:

```bash
docker compose --profile crawlers up -d scheduler crawler-admin
```

That profile starts:

- `scheduler` for `python crawler_scheduler.py`
- `crawler-admin` for `python crawler_admin_server.py`
- the admin UI on `http://localhost:3010/admin`

In this container profile, Compose reads crawler secrets from `crawler/.env`
via `env_file`, while the admin service persists scheduler edits back to the
mounted `CRAWLER_CONFIG.yml`.

If you want these mutable runtime files outside the repository checkout, set
`OEDS_RUNTIME_DIR` before starting Compose.

To stop the stack:

```bash
docker compose down
```

## Prepare the Python environment

Sync the crawler environment from the repository root:

```bash
uv sync --locked
```

This full host-side environment includes native dependencies such as `pygrib`.
On Windows, Docker or WSL is usually simpler unless `ecCodes` is already
available locally.

## Configure crawlers

The scheduler and helper scripts read crawler settings from `CRAWLER_CONFIG.yml`
in the repository root.

Typical local preparation:

1. review the crawler-specific section in `CRAWLER_CONFIG.yml`
2. set the target `database_uri` and `schema_name`
3. add local secrets to `crawler/.env` if the crawler needs authentication
4. narrow initial backfill windows before enabling credentialed crawlers such
   as `entsoe_fms`

Common secrets used in this repository include:

- `ENTSOE_USERNAME`
- `ENTSOE_PASSWORD`
- `ENERGY_FORECAST_TOKEN`

## Run a single crawler

Run crawlers from the repository root with `python -m`:

```bash
uv run python -m crawler.weather_forecast
uv run python -m crawler.entsoe_fms
uv run python -m crawler.energy_forecast_crawler
```

Use single-crawler runs for first loads, debugging, and source-specific tests.
On a clean install, this is also how crawler-created schemas such as `weather`
appear for the first time.

## Run the scheduler

To start the scheduler loop:

```bash
uv run python crawler_scheduler.py
```

The scheduler reads `CRAWLER_CONFIG.yml` and executes enabled crawlers according
to their cron schedules.

To start the admin UI directly on the host:

```bash
uv run python crawler_admin_server.py
```

Both host-side entry points automatically load `crawler/.env` when it exists.

When the scheduler or admin UI runs in Docker, Compose injects the internal
database target so the existing `localhost:6432` values in
`CRAWLER_CONFIG.yml` do not need to be rewritten just for containerized runs.

The same Compose file also supports `OEDS_RUNTIME_DIR` so deployments can keep
`CRAWLER_CONFIG.yml`, `crawler/.env`, logs, and admin state outside the Git
working tree.

## Local service access

### PgAdmin

Default development credentials:

- username: `admin@admin.admin`
- password: `admin`

If auto-provisioning does not show the server, register it manually with the
same local database credentials that are defined in `compose.yml`.

### PostgREST

PostgREST exposes database objects as HTTP endpoints at
`http://localhost:3001/`.

Objects outside the `public` schema may require additional headers or explicit
schema selection, depending on how the API consumer is configured.

### Grafana

Default development credentials:

- username: `opendata`
- password: `opendata`

Provisioned dashboards live under `data/provisioning/grafana/dashboards/` and
are grouped into crawler-specific subfolders plus `shared/`.
Many dashboards stay empty until their related crawlers have populated the
target schemas. On a clean installation, that means the dashboard panels only
become meaningful after the first successful crawler run.

## Where to go next

- crawler-specific notes: [Crawler Documentation](./crawlers/README.md)
- deployment on a long-lived host: [Deployment Guide](./deployment.md)
- scheduler options: [Crawler Configuration](./crawler_config.md)
- maintained examples: [Examples](examples/index)
