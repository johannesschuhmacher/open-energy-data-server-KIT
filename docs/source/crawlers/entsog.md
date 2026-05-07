# `entsog`

## Purpose

`crawler.entsog` imports ENTSOG transparency platform reference data and
selected operational gas datasets into the `entsog` schema.

It is intended for:

- gas transmission network reference data
- balancing zone and connection point lookups
- physical flow and allocation time series
- firm technical capacity monitoring

## Source system and authentication

- Source system: ENTSOG transparency platform API
- Authentication: none

The crawler currently uses the public API endpoints for reference and
operational data and does not require local secrets.

## How to run it manually

From the repository root:

```shell
python -m crawler.entsog
```

## Scheduler configuration

The crawler is configured under the `entsog` key in `CRAWLER_CONFIG.yml`.

Important options:

- `enable`
- `schema_name`
- `database_uri`
- `schedule`
- `default_start_date`
- `chunk_days`
- `request_pause_seconds`

Current default entry:

```yaml
entsog:
  enable: false
  schema_name: "entsog"
  schedule: "30 2 * * *"
  default_start_date: "2024-01-01"
  chunk_days: 7
  request_pause_seconds: 1.0
```

`default_start_date` controls the first historical backfill window for the
operational tables. `chunk_days` splits large historical loads into bounded API
windows, and `request_pause_seconds` can be increased if the upstream API needs
throttling.

## Output schema and tables

The crawler writes to schema `entsog`.

Reference tables:

- `operators`
- `connectionpoints`
- `balancingzones`
- `operatorpointdirections`
- `interconnections`
- `aggregateinterconnections`

Operational tables:

- `physical_flow`
- `allocation`
- `firm_technical`

## Downstream dependencies

Known downstream consumer:

- `ENTSOG-Monitor`

The schema is also available for PostgREST, SQL analysis, and custom Grafana
queries.

## Operational notes

- The crawler uses the current ENTSOG API endpoint naming and normalizes mixed
  timezone payloads before writing to PostgreSQL.
- A first historical run can still be large, so narrow `default_start_date`
  when you only need a short initial validation window.
- The current operational coverage focuses on the indicators already used by
  the repository dashboards: physical flow, allocation, and firm technical
  capacity.
