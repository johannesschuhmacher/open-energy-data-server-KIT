# Troubleshooting

This page collects the most common operator problems in OEDS-KIT and the
fastest checks to resolve them.

## Grafana shows dashboards but no data

Typical causes:

- the related crawler has not run successfully yet
- the dashboard points to a schema that is still empty
- the crawler credentials are missing and imports failed
- the dashboard reads a derived schema such as a gapfill target schema that has
  not been populated yet

Recommended checks:

1. Open the crawler in the admin UI and inspect the latest run status and log.
2. Query `public.metadata` in PostgreSQL to confirm which schemas and tables
   have actually been created.
3. In PgAdmin or SQL, check whether the expected schema has rows.
4. For gapfill dashboards, check both the raw source schema and the derived
   target schema such as `entsoe_fms_gapfilled`.

## The admin UI is reachable but no crawler data appears

This usually means the UI itself is healthy but the crawler runtime has not
imported anything yet.

Check:

- whether the crawler is enabled in `CRAWLER_CONFIG.yml`
- whether the schedule or `jobs` block is valid
- whether required credentials exist in `crawler/.env`
- whether the database target is reachable from the current runtime mode
  (host-side versus Docker)

For a first load, prefer a one-off manual run from the admin UI or a direct
host-side command such as:

```bash
uv run python -m crawler.weather_forecast
```

## A crawler fails immediately because credentials are missing

The repository intentionally ships without live source credentials.

Typical examples:

- `ENTSOE_USERNAME`
- `ENTSOE_PASSWORD`
- `ENTSOE_API_KEY`
- `ENERGY_FORECAST_TOKEN`
- `EPEX_SFTP_USERNAME`
- `EPEX_SFTP_PASSWORD`

Put these values into `crawler/.env` for local or containerized crawler runs.
On long-lived deployments, keep the runtime `.env` outside the Git working tree
when possible.

For ENTSO-E, distinguish the two credential paths: `entsoe_fms` uses
`ENTSOE_USERNAME` and `ENTSOE_PASSWORD`; `entsoe_api` uses the separate
`ENTSOE_API_KEY` security token. `ENTSOE_API` is accepted as a local alias for
that token. The API-backed price forecast job requires this token.

## PostgreSQL or TimescaleDB was upgraded and the container no longer starts

Moving between PostgreSQL major versions is not an in-place image swap.

If the data directory was created by an older major version, plan a migration
before pointing PostgreSQL 18 at it. Supported approaches include:

- `pg_upgrade`
- dump and restore
- full environment migration through backup and restore

Do not reuse an older PostgreSQL data directory with the new image without a
migration step.

## Gapfill is configured but the dashboard stays empty

Gapfill has two different paths:

- **productive gapfill operations** on the crawler detail page
- **Gapfill Tests** under `/admin/gapfill`

Important distinction:

- the admin test page runs synthetic checks in-process and does not persist them
  automatically
- the productive post-run gapfill writes derived tables and control tables to
  the configured target schema
- the Grafana dashboard reads the persisted target schema data, not the
  process-local admin preview

If the gapfill dashboard is empty, confirm:

1. the crawler detail page has the gapfill post-run script enabled
2. at least one source table is selected for productive gapfill
3. the target schema exists and contains `gapfill_runs`, `gapfill_metrics`, or
   related QA tables

## The scheduler and admin UI see different database targets

This is usually an environment mismatch.

- Host-side runs read the database URI from `CRAWLER_CONFIG.yml` and optional
  local environment overrides.
- Dockerized runs inject container-friendly database host and port overrides.

The same YAML can still work in both modes, but only if the runtime helper
functions resolve the database URI correctly. When debugging, always check
whether the failing process runs:

- directly on the host
- inside the `scheduler` container
- inside the `crawler-admin` container

## Where to continue

- setup and local stack: [Getting Started](./getting_started.md)
- server deployment: [Deployment Guide](./deployment.md)
- scheduler, runs, and gapfill controls: [Crawler Admin UI](./crawler_admin.md)
- post-run behavior: [Post-Run Scripts](./post_run_scripts.md)
