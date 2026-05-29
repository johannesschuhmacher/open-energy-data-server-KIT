# Crawler Configuration

The scheduler reads crawler settings from `CRAWLER_CONFIG.yml` in the repository
root. Each top-level key matches one crawler module name such as
`entsoe_fms`, `entsoe_api`, `weather_forecast`, or
`energy_forecast_crawler`.

## Defaults and overrides

The `default` section defines shared values for all crawlers. A crawler-specific
section can override any of these values.

Example:

```yaml
default:
  enable: false
  schedule: "0 4 * * *"
  database_uri: "postgresql://user:pass@host:5432/opendata?options=--search_path="

weather_forecast:
  enable: true
  schema_name: "weather"
  schedule: "15 */3 * * *"
  forecast_hours: 120
```

## Common options

Most crawlers use some or all of these options:

- `enable`: enable or disable the crawler in the scheduler
- `schedule`: cron expression used by the scheduler
- `schema_name`: target PostgreSQL schema
- `database_uri`: target PostgreSQL connection string
- `post_run_scripts`: scripts that should run after the crawler; see
  [Post-Run Scripts](post_run_scripts.md)
- `description`: short human-readable description
- `email`: optional notification settings for critical failures. Crawler
  critical emails are rate-limited to one message per crawler and subject per
  hour by default; set `email.rate_limit_seconds` or
  `email.rate_limit_minutes` to tune this.
- `logging`: optional crawler log rotation settings. Runtime log files rotate
  at 100 MiB with 5 retained backups by default. Set `logging.max_bytes` and
  `logging.backup_count`, or the environment variables
  `OEDS_LOG_FILE_MAX_BYTES` and `OEDS_LOG_FILE_BACKUP_COUNT`, to tune this.
  Log files older than 30 days are removed from the runtime `logs/` directory
  by default. Set `logging.retention_days` or `OEDS_LOG_RETENTION_DAYS` to tune
  this; use `0` to disable age-based cleanup.

List values are replaced completely when overridden. Dictionary values are
merged key-by-key.

## Multiple scheduler jobs

A crawler can define a `jobs` mapping when it needs more than one schedule.
Each job inherits the crawler's effective settings and can override options such
as `schedule`, `target_data_items`, or crawler-specific window settings.

Example:

```yaml
entsoe_fms:
  enable: true
  schema_name: "entsoe_fms"
  jobs:
    latest_hourly:
      enable: true
      schedule: "0 * * * *"
      mode: "fms_package_refresh"
      fms_package_window_months: 1
      fms_package_write_mode: "full_upsert"
      run_post_scripts: true
      target_data_items:
        - "ActualTotalLoad_6.1.A_r3"

    revision_sweep_daily:
      enable: true
      schedule: "30 2 * * *"
      mode: "fms_package_refresh"
      fms_package_window_months: 3
      fms_package_write_mode: "full_upsert"
      run_post_scripts: true
      target_data_items:
        - "ActualTotalLoad_6.1.A_r3"
```

When `jobs` is present, the scheduler runs named jobs such as
`entsoe_fms:latest_hourly`. Crawler sections without `jobs` keep the legacy
single-schedule behavior.

In the Crawler Admin UI, named jobs can be edited one at a time in the schedule
dialog. The dialog updates only the selected job's `enable` and `schedule`
values. Use the YAML editor for wider job changes, for example `target_data_items`,
window sizes, or crawler-specific modes.

The scheduler uses an in-memory queue. It does not enqueue the same job again
while that job is already queued or running. For `entsoe_fms`, locks are based
on the target tables derived from `target_data_items`, so jobs touching the same
tables wait for each other while non-overlapping jobs can run in parallel.

## Crawler-specific options

Many crawlers define additional options. Examples:

- `weather_forecast`: `forecast_hours`, `past_hours`, `locations`
- `entsoe_fms`: `target_data_items`, `fms_package_window_months`,
  `fms_package_write_mode`
- `entsoe_api`: `country_code`, `lookback_days`, `lookahead_days`,
  `target_datasets`
- source-specific tokens or credentials loaded from `crawler/.env`

Crawler-specific behavior should be documented on the crawler page under
`docs/source/crawlers/`.

## Notes

- `CRAWLER_CONFIG.yml` is used by the scheduler and helper scripts.
- Secret values should not be committed. Keep them in `crawler/.env` or another
  local environment mechanism.
- In Docker-based OEDS runs, `OEDS_DB_PASSWORD` can override the password part
  of the configured `database_uri` at runtime so the public example URIs can
  stay generic.
- The main scheduler entry point is `crawler_scheduler.py`.
