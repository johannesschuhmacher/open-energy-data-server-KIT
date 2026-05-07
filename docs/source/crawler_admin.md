# Crawler Admin UI

The crawler admin UI is a local control surface for `CRAWLER_CONFIG.yml` and
manual crawler operations.

Implemented phases:

- read-only dashboard for configured and discoverable crawler modules
- compact schedule cards with a modal editor for `enable` and `schedule`
- denser operations list with search, quick filters, and collapsible crawler rows
- recurrence editor with `Hourly`, `Daily`, `Weekly`, and `Advanced` modes
- CRON preview for effective schedules
- raw YAML editor with validation and save conflict detection
- manual one-off execution from the dashboard and crawler detail pages without changing the scheduler
- dashboard `Run Once` opens a confirmation dialog with the current crawler configuration before execution
- email alert status and testing moved into the crawler-specific `Settings & Details` view
- run history with persistent status tracking
- live log tailing for active and completed runs
- in-process locking so the same crawler cannot be started twice at once
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
- the next three local run times for each effective CRON schedule
- latest manual run status and lock state
- a search field plus quick filters for `Enabled`, `Disabled`, `Running`, and `Issues`
- a three-level flow:
  - collapsed row with next schedule, run state, and status
  - expandable summary with a reduced operational overview
  - dedicated `Settings & Details` page for alerts, config, actions, history, and logs
- a modal schedule editor opened from the dashboard

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

Cards intentionally distinguish between:

- modules that exist but are not yet configured
- crawler sections that are configured and enabled
- crawler sections that are configured but disabled
- sections that need attention because validation found issues

## YAML validation rules

The editor validates the file before saving. Phase 1 checks:

- YAML syntax
- presence and type of the top-level `default` section
- crawler sections being mappings
- valid effective `schedule`
- valid effective `enable`
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
