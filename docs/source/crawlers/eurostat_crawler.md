# `eurostat_crawler`

## Purpose

`crawler.eurostat_crawler` imports selected Eurostat datasets into the
`eurostat` schema.

The current default configuration targets dataset `nrg_inf_epcrw`, which the
crawler reshapes into a tabular format suitable for PostgreSQL and TimescaleDB.

This crawler is useful for:

- annual European energy statistics
- cross-country comparisons
- reference series that complement operational market data

## Source system and authentication

- Source system: Eurostat
- Upstream site: `https://ec.europa.eu/eurostat`
- Python client: `eurostat`
- Authentication: none

## How to run it manually

From the repository root:

```shell
python -m crawler.eurostat_crawler
```

## Scheduler configuration

The crawler is configured under the `eurostat_crawler` key in
`CRAWLER_CONFIG.yml`.

Important options:

- `enable`
- `schema_name`
- `database_uri`
- `dataset_id`
- `table_name` (optional explicit override)
- `start_year`
- `end_year`

Current default entry:

```yaml
eurostat_crawler:
  enable: false
  schema_name: "eurostat"
  dataset_id: "nrg_inf_epcrw"
  start_year: 2019
  end_year: 2025
```

## Output schema and tables

The crawler writes to schema `eurostat`.

Current default table:

- `eurostat`

If `dataset_id` is changed away from the legacy default `nrg_inf_epcrw`, the
crawler writes to `eurostat_<dataset_id>` after identifier sanitization, unless
`table_name` is set explicitly.

The table is keyed by a unique constraint across:

- `year`
- `geo\TIME_PERIOD`
- `siec`
- `plant_tec`

The crawler performs upserts so that repeated runs refresh existing year-country
combinations instead of blindly appending duplicates.

## Downstream dependencies

The repository currently does not provision a dedicated Eurostat dashboard.

Typical uses are:

- long-term context for energy dashboards
- country-level comparison notebooks
- joining annual statistics with operational ENTSO-E or weather data

## Operational notes

- The legacy default dataset `nrg_inf_epcrw` keeps the historical table name
  `eurostat` so existing downstream SQL does not break.
- Alternative compatible dataset ids are isolated into dataset-specific table
  names unless `table_name` overrides that behavior.
- The crawler reshapes wide year columns into a long format before writing to
  PostgreSQL.
- The requested `start_year` and `end_year` window is intersected with the year
  columns actually returned by the upstream dataset.
- Because this is annual data, the TimescaleDB hypertable is mainly a
  consistency choice rather than a high-frequency requirement.
