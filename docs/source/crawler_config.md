# Crawler Configuration

The scheduler reads crawler settings from `CRAWLER_CONFIG.yml` in the repository
root. Each top-level key matches one crawler module name such as
`entsoe_fms`, `weather_forecast`, or `energy_forecast_crawler`.

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
- `email`: optional notification settings for critical failures

List values are replaced completely when overridden. Dictionary values are
merged key-by-key.

## Crawler-specific options

Many crawlers define additional options. Examples:

- `weather_forecast`: `forecast_hours`, `past_hours`, `locations`
- `entsoe_fms`: `target_data_items`
- source-specific tokens or credentials loaded from `crawler/.env`

Crawler-specific behavior should be documented on the crawler page under
`docs/source/crawlers/`.

## Notes

- `CRAWLER_CONFIG.yml` is used by the scheduler and helper scripts.
- Secret values should not be committed. Keep them in `crawler/.env` or another
  local environment mechanism.
- The main scheduler entry point is `crawler_scheduler.py`.
