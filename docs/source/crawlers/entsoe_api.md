# entsoe_api

## Purpose

`crawler.entsoe_api` imports selected ENTSO-E Transparency Platform Web API
time series into PostgreSQL.

It complements `entsoe_fms`. The FMS crawler is still the preferred source for
large package refreshes and historical completeness. This API crawler is for
small, fresh refresh windows that downstream jobs can run shortly before
forecasting.

Currently supported datasets:

- SDAC day-ahead prices
- EXAA day-ahead prices as ENTSO-E price sequence `2`
- day-ahead total load forecast
- wind and solar generation forecast

## Source system and authentication

The crawler reads from the ENTSO-E Transparency Platform Web API:

`https://web-api.tp.entsoe.eu/api`

Required credential:

- `ENTSOE_API_KEY`

`ENTSOE_SECURITY_TOKEN` and `ENTSOE_API` are accepted as alternative environment
variable names. Set the token as an environment variable or in `crawler/.env`.
Do not commit real tokens.

This token is not the same secret as the FMS crawler credentials. `entsoe_fms`
uses `ENTSOE_USERNAME` and `ENTSOE_PASSWORD` for the File Library login; the
Web API crawler uses a generated Transparency Platform security token. The
day-ahead price forecast is triggered from `entsoe_api`, so productive forecast
deployments need this API token.

## How to run it manually

Run from the repository root:

```shell
python -m crawler.entsoe_api
```

The manual entry point uses schema `entsoe_api`, market area `DE_LU`, a
14-day lookback, and a 2-day lookahead. Scheduled runs should use
`CRAWLER_CONFIG.yml`.

## Scheduler configuration

The crawler is configured under the `entsoe_api` key in `CRAWLER_CONFIG.yml`.

Important options:

- `enable`
- `schema_name`
- `schedule`
- `post_run_scripts`
- `country_code`
- `start_date`
- `lookback_days`
- `lookahead_days`
- `request_pause_seconds`
- `include_day_ahead_prices`
- `include_exaa_prices`
- `include_load_forecast`
- `include_wind_solar_forecast`
- `target_datasets`

`target_datasets` can restrict a run to selected datasets. Valid dataset names
are:

- `day_ahead_prices`
- `exaa_day_ahead_prices`
- `load_forecast`
- `wind_solar_forecast`

The default committed scheduler path is enabled through
`entsoe_api:forecast_daily` and set to `35 11 * * *`. This is a useful
pre-auction refresh point for price forecasting, but operators should adjust it
to their auction and API-token timing needs.

The committed `post_run_scripts` list runs
`scripts/run_price_forecast.py` after a successful API refresh. During early
deployments the script records skipped runs instead of failing when there is not
yet enough historical training data.

`entsoe_api` also contains a disabled `training_bootstrap` job with a larger
`lookback_days` window. Use it manually or enable it once on a clean deployment
to populate enough API history for model training; it does not run the forecast
post-run script.

The forecast post-run checks how much API SDAC and EXAA history is available.
If the API history is still too short, it trains on FMS history and uses API
rows for fresh delivery intervals where available. Once enough API history is
present, the same post-run path switches to API-backed training automatically.

## Output schema and tables

The crawler writes to schema `entsoe_api`.

Tables:

- `day_ahead_prices`
- `load_forecasts`
- `wind_solar_forecasts`

`day_ahead_prices` stores both SDAC and EXAA rows. The `source_market` column
contains `SDAC` or `EXAA`, and `sequence` keeps the ENTSO-E sequence used for
the API request.

All writes use conflict-safe upserts, so repeated scheduled runs can refresh
the same delivery intervals without duplicating rows.

## Downstream dependencies

The provisioned dashboard
`ENTSOE API - Fresh Market Data` reads from schema `entsoe_api`.

The intended downstream use is the OEDS day-ahead price forecasting post-run
pipeline. That pipeline reads this schema as its primary source and may still
fall back to `entsoe_fms` or `entsoe_fms_gapfilled` for historical training data
while API history warms up.

## Operational notes

- This crawler does not replace `entsoe_fms`; it is intentionally narrow and
  refresh-oriented.
- Keep `lookback_days` small for routine runs. Use FMS package refreshes for
  large historical imports.
- If EXAA data appears late, schedule a second run or trigger this crawler from
  the admin UI before the forecasting post-run script.
- ENTSO-E API availability and data-release timing can vary by dataset. Missing
  datasets are logged and do not delete existing rows.
