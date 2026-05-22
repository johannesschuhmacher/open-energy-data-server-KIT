# Crawler Admin UI

The crawler admin UI is a local control surface for `CRAWLER_CONFIG.yml` and
manual crawler operations.

Implemented phases:

- read-only dashboard for configured and discoverable crawler modules
- compact schedule cards with a modal editor for `enable` and `schedule`
- multi-job schedule previews for crawler sections that define `jobs`
- denser operations list with search, quick filters, and collapsible crawler rows
- recurrence editor with `Hourly`, `Daily`, `Weekly`, and `Advanced` modes
- CRON preview for effective schedules
- raw YAML editor with validation and save conflict detection
- manual one-off execution from the dashboard and crawler detail pages without changing the scheduler
- dashboard `Run Once` opens a confirmation dialog with the current crawler configuration before execution
- email alert status and testing moved into the crawler-specific `Settings & Details` view
- run history with persistent status tracking
- runtime benchmarks per manual action based on completed run durations
- live log tailing for active and completed runs
- in-process locking so the same crawler cannot be started twice at once
- separate Gapfill Tests page for synthetic fault injection, gapfill self-tests,
  and source-versus-filled series previews
- crawler-specific operation forms for:
  - `weather_forecast`
  - `eurostat_crawler`
  - `entsoe_fms`

The UI does not replace the YAML file. `CRAWLER_CONFIG.yml` remains the source
of truth that the scheduler reads.

## Start the UI

Install the Python dependencies first:

```bash
uv sync --locked
```

Then start the admin server from the repository root:

```bash
uv run python crawler_admin_server.py
```

The server loads `crawler/.env` automatically when that file exists.

By default the UI is available at `http://127.0.0.1:3010/admin`.

To run the same UI in Docker together with the optional crawler profile:

```bash
docker compose --profile crawlers up -d crawler-admin
```

The containerized admin service keeps writing scheduler changes back to the
same bind-mounted `CRAWLER_CONFIG.yml` and stores its run database under
`crawler_admin_state/`. In the provided Compose profile it is configured with
write access to the runtime config mount so YAML saves and schedule edits work
on long-lived hosts as well.

When the UI runs in Docker, crawler secrets still come from the host-side
`crawler/.env` through Compose `env_file`; they are not edited through the UI.

Optional environment variables:

- `OEDS_ADMIN_HOST`
- `OEDS_ADMIN_PORT`
- `OEDS_ADMIN_RELOAD`
- `OEDS_ADMIN_STATE_DIR`

Example:

```bash
OEDS_ADMIN_PORT=3011 uv run python crawler_admin_server.py
```

## What the dashboard shows

The dashboard combines:

- crawler modules discovered under `crawler/`
- configured crawler sections from `CRAWLER_CONFIG.yml`
- merged default values where applicable
- the next local run times for each effective CRON schedule or named scheduler job
- latest manual run status and lock state
- a search field plus quick filters for `Enabled`, `Disabled`, `Running`, and `Issues`
- a three-level flow:
  - collapsed row with next schedule, run state, and status
  - expandable summary with a reduced operational overview
  - dedicated `Settings & Details` page for alerts, config, actions, history, and logs
- a modal schedule editor opened from the dashboard

Crawler sections with a `jobs` mapping, such as the ENTSO-E FMS package-refresh
setup, are shown as multiple named schedules. The compact modal editor is kept
for legacy single-schedule crawlers; multi-job schedules are edited in the raw
YAML editor so the job-specific overrides stay explicit.

Local email recipient overrides:

- the admin UI and scheduler still read `CRAWLER_CONFIG.yml` as the source of truth
- local operators can override `default.email.toaddrs` through `crawler/.env`
- use `OEDS_EMAIL_TOADDRS=person1@example.com,person2@example.com` for local test routing without changing committed YAML
- the same local override file also supports `OEDS_EMAIL_MAILHOST`, `OEDS_EMAIL_FROMADDR`, `OEDS_EMAIL_SUBJECT`, `OEDS_EMAIL_USERNAME`, and `OEDS_EMAIL_PASSWORD`
- the committed `CRAWLER_CONFIG.yml` should stay neutral and not contain personal or institution-specific email routes

Dashboard scheduler edits:

- write `enable` and `schedule` directly back to `CRAWLER_CONFIG.yml`
- validate CRON expressions before saving
- show a live preview of the next three runs while editing
- create a minimal crawler section when a module exists without YAML yet
- use exclusive recurrence modes so only the active mode contributes to the generated CRON
- support compact recurrence forms for hourly, daily, and weekly schedules
- allow weekday selection with individual weekday chips in weekly mode
- fall back to advanced CRON mode when an existing schedule cannot be mapped safely
- direct operators to the YAML editor when a crawler uses named scheduler jobs

Cards intentionally distinguish between:

- modules that exist but are not yet configured
- crawler sections that are configured and enabled
- crawler sections that are configured but disabled
- sections that need attention because validation found issues

## Gapfill Tests

The `Gapfill Tests` navigation item opens `/admin/gapfill`. Operators can run the
synthetic gapfiller self-tests from the admin UI without touching raw crawler
tables.

This page is intentionally separate from the productive gapfill controls. The
productive settings live on the crawler detail page for the corresponding job.
There, operators decide whether the post-run gapfill script runs at all, which
source tables are included, and which derived schema receives the gapfilled
copies and QA metadata used by Grafana. The table list is a built-in metadata
allowlist for supported time-series tables, not an unconstrained database table
browser. When the configured database is reachable, the detail page also marks
whether each supported source table currently exists. Each selected table can
override the default gapfill method.

The self-test catalog currently covers:

- value gaps in an otherwise complete hourly series
- missing timestamps that must be recreated before values can be imputed
- daily seasonal value gaps filled by `donor_refined`

Each run injects the selected faults into synthetic data, calls the same
gapfiller core used by `scripts/gapfill_timeseries.py`, checks the expected fill
counts, and renders source and gapfilled series previews with imputed points
marked.

The same page also contains a holdout error test. Operators select a synthetic
time-series dataset, the start index, the number of periods to remove, the
removal type (`value_gap` or `timestamp_gap`), and the gapfill method. The test
removes that known data segment, fills it, and compares the imputed values with
the held-out original values. The UI reports MAE, RMSE, maximum absolute error,
MAPE, compared point count, and filled point count.

The CLI self-test path remains available through:

```bash
uv run python scripts/gapfill_timeseries.py --job entsoe_fms --self-test
```

The CLI writes the same synthetic QA results to the configured gapfill target
schema for Grafana dashboards. The admin page keeps the latest run in the admin
process so it is useful for quick local demonstrations and regression checks.

Real database holdout tests are executed through
`scripts/gapfill_timeseries.py --holdout-test`. They read real source rows,
remove the selected segment only in memory, compare the filled values with the
held-out truth, and write QA rows to the gapfill target schema. Grafana displays
these results in `OEDS Gapfilling Quality`.

## YAML validation rules

The editor validates the file before saving. Phase 1 checks:

- YAML syntax
- presence and type of the top-level `default` section
- crawler sections being mappings
- valid effective `schedule`
- valid job-level `schedule` values when a crawler uses `jobs`
- valid effective `enable`
- valid job-level `enable` values when a crawler uses `jobs`
- presence of effective `schema_name`
- presence of effective `database_uri`
- `post_run_scripts` being a list when present

Validation warnings and errors are shown before a save is accepted.

## Conflict detection

The editor stores a hash of the file version that was loaded. If the file
changes on disk before the save request arrives, the UI blocks the save and
asks the operator to reload first.

That prevents accidental overwrites when the YAML is being edited in another
terminal or editor while the admin page is open.

## Manual run storage

Manual runs are persisted in a small SQLite database together with a dedicated
log file per run.

By default the admin service stores this state in a local user directory. Use
`OEDS_ADMIN_STATE_DIR` to override the location.

The run store contains:

- action id and label
- run status
- timestamps and duration
- temporary overrides used for the action
- a dedicated log file path

The crawler detail page derives runtime benchmarks from the same run store.
For each manual action it shows sample count, success rate, and the latest
completed duration.

On a clean installation, a first manual run can also bootstrap crawler-owned
schemas and metadata entries. The validated weather deployment path uses this
behavior to create and populate the `weather` schema before dashboard panels
become useful.

## Specialized actions

The crawler detail page exposes crawler-specific forms where phase 3 is already
implemented:

- `weather_forecast`: temporary `forecast_hours`, `past_hours`, and optional
  location id subset
- `eurostat_crawler`: temporary `dataset_id`, `start_year`, and `end_year`
- `entsoe_fms`: targeted runs via `target_data_items` and historical backfills
  for monthly, annual, or single-file extracts
- `entsoe_api`: on-demand day-ahead price forecast runs and self-tests
- supported gapfill jobs: manual gapfill backfills for an explicit source
  timestamp window

The `entsoe_api` detail page also shows whether
`scripts/run_price_forecast.py` is attached as a post-run script and lists the
latest rows from `price_forecast.forecast_runs` when the database is reachable.
The manual Price forecast action exposes target date, training window,
backtest days, and model backend without editing YAML.

The manual gapfill backfill action calls `scripts/gapfill_timeseries.py` with
`--start` and optional `--end`. It reprocesses the configured source tables for
that time window and writes the derived gapfilled target tables plus
`gapfill_runs` and `gapfill_metrics` rows. It intentionally does not advance
`gapfill_tracking`, so a historical backfill cannot move the normal
incremental post-run watermark backwards.
