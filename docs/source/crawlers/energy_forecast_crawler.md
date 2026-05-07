# `energy_forecast_crawler`

## Purpose

`energy_forecast_crawler` pulls the next 48 hours of quarter-hourly retail or
trading price forecasts from `energyforecast.de` and stores them in the
`energy_forecast` schema.

## Source system and authentication

- Source API: `https://www.energyforecast.de/api/v1/predictions/next_48_hours`
- Authentication: token-based
- Required secret: `ENERGY_FORECAST_TOKEN`

The crawler loads the token from `crawler/.env` when that file exists.

## How to run it manually

From the repository root:

```shell
python -m crawler.energy_forecast_crawler
```

## Scheduler configuration

The crawler is configured under the `energy_forecast_crawler` key in
`CRAWLER_CONFIG.yml`.

Important options:

- `schema_name`
- `database_uri`
- `schedule`

The current scheduler entry runs twice per day.

## Output schema and tables

The crawler writes to schema `energy_forecast`.

Primary table:

- `predictions_48h`

The table stores one row per forecast start time and expands the 48-hour
quarter-hourly horizon into price columns `p_h_*` and origin columns `o_h_*`.

The crawler also appends a local history file to:

- `crawler/data/energy_forecast_history.csv`

## Downstream dependencies

There is currently no dedicated provisioned Grafana dashboard for this schema in
the repository. The crawler mainly provides a reusable forecast table for
downstream analysis or custom dashboards.

## Operational notes

- The upstream API is proprietary, so public installs need their own token.
- The crawler currently requests the `DE-LU` market zone in quarter-hourly
  resolution.
- The table uses an upsert on `prediction_start`, so repeated runs refresh the
  same forecast start if the API republishes it.
- The crawler now fails fast when `ENERGY_FORECAST_TOKEN` is missing or the API
  returns no usable forecast rows.
