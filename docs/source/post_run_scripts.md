# Post-Run Scripts

OEDS crawlers can run follow-up scripts after a crawler finished successfully.
These scripts are configured with `post_run_scripts` in `CRAWLER_CONFIG.yml`.

Post-run scripts are intended for derived data and maintenance work that depends
on freshly imported crawler data, for example:

- filling gaps in regular time-series tables
- refreshing derived SQL views or materialized helper tables
- rebuilding dashboard support tables
- exporting validation or quality metrics

Post-run scripts must not be used for crawler credentials, long-running initial
backfills, or source ingestion. Those tasks belong in the crawler itself or in a
manual maintenance script.

## Configuration

`post_run_scripts` is a list of repository-relative Python script paths:

```yaml
entsoe_fms:
  enable: true
  post_run_scripts:
    - "scripts/gapfill_timeseries.py"
    - "scripts/refresh_entsoe_availability_map.py"
```

List values are replaced when crawler-specific config is merged with
`default`. If a crawler defines its own `post_run_scripts`, it owns the complete
ordered list for that crawler.

## Execution Order

Scripts run in the order listed in `CRAWLER_CONFIG.yml`.

For the ENTSO-E FMS crawler this matters:

1. `scripts/gapfill_timeseries.py` creates or refreshes gapfilled copies of
   selected time-series tables.
2. `scripts/refresh_entsoe_availability_map.py` refreshes derived availability
   map objects after the raw crawler import.

If a later script depends on output from an earlier script, keep that dependency
explicit in the list order.

## Runtime Environment

Post-run scripts are started from the repository root. They should use paths
relative to the repository root and should read shared settings from
`CRAWLER_CONFIG.yml` rather than from hard-coded local files.

Crawler services load `crawler/.env` before execution. Docker services also set
database host and port overrides:

- `OEDS_DB_HOST`
- `OEDS_DB_PORT`

Scripts that need a database connection should use
`crawler.common.runtime_env.resolve_database_uri()` so the same
`CRAWLER_CONFIG.yml` works on the host and inside Docker.

## Failure Semantics

The crawler admin runtime executes post-run scripts with the current Python
interpreter and checks the script return code. A non-zero return code marks the
run as failed.

The scheduler currently invokes post-run scripts through the configured Python
command path and logs the execution. New post-run scripts should still return a
non-zero exit code on failure so the admin UI and future scheduler handling can
surface failures consistently.

## Operational Rules

- Keep raw crawler tables immutable. Write derived output to separate schemas or
  tables.
- Make scripts idempotent. Re-running the same script should not duplicate
  output rows.
- Store run metadata and quality metrics where dashboards can read them.
- Keep secrets out of committed `.env` files and out of script source code.
- Prefer bounded incremental windows over full-table recomputation.
- Use parametrized SQL for values; only quote identifiers manually when needed.

## Testing Post-Run Gapfilling

The generic time-series gapfiller includes synthetic self-tests. They inject
controlled faults into in-memory series, run the same gapfill core that the
post-run script uses, and assert the expected number of imputed values.

For database-backed dashboard data:

```bash
uv run python scripts/gapfill_timeseries.py --job entsoe_fms --self-test
```

For an interactive local check, open the crawler admin UI and use
`/admin/gapfill`. The admin view lets operators select fault scenarios and
renders source-versus-filled previews without writing synthetic data to the
database.

The admin UI also has a holdout error test for gapfilling. Select a synthetic
time-series dataset, remove a configurable number of periods from a configurable
start index, fill the resulting gap, and compare the result with the held-out
truth. This reports MAE, RMSE, maximum absolute error, MAPE, compared points,
and filled points.

For real database data, use the holdout mode of the post-run script:

```bash
uv run python scripts/gapfill_timeseries.py \
  --job entsoe_fms \
  --holdout-test \
  --holdout-table ActualTotalLoad \
  --holdout-value-column "TotalLoad[MW]" \
  --holdout-start "2026-04-01T00:00:00Z" \
  --holdout-length 24
```

This reads real source rows, removes the selected segment only in memory, and
writes QA output to the gapfill target schema for Grafana. It does not modify
raw crawler tables.

## Current Post-Run Scripts

| Script | Main crawler | Purpose |
|---|---|---|
| `scripts/gapfill_smard.py` | `smard` | Legacy SMARD gapfill helper |
| `scripts/gapfill_timeseries.py` | `entsoe_fms` | Generic OEDS time-series gapfilling |
| `scripts/refresh_entsoe_availability_map.py` | `entsoe_fms` | Refresh ENTSO-E availability map SQL objects |
| `scripts/run_price_forecast.py` | `entsoe_api` | Build derived day-ahead price forecasts in `price_forecast` |
