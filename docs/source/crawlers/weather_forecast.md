# `weather_forecast`

## Purpose

`weather_forecast` fetches hourly DWD ICON weather forecasts via the Open-Meteo
DWD endpoint and stores them in the `weather` schema. It is intended to support
weather-only dashboards and cross-domain comparisons with energy data.

## Source system and authentication

- Source API: Open-Meteo DWD endpoint
- Endpoint: `https://api.open-meteo.com/v1/dwd-icon`
- Upstream docs: `https://open-meteo.com/en/docs/dwd-api`
- Authentication: none

## How to run it manually

From the repository root:

```shell
python -m crawler.weather_forecast
```

## Scheduler configuration

The crawler is configured under the `weather_forecast` key in
`CRAWLER_CONFIG.yml`.

Important options:

- `schema_name`
- `database_uri`
- `schedule`
- `forecast_hours`
- `past_hours`
- `locations`

The current default scheduler entry uses a three-hour cadence.

## Output schema and tables

The crawler writes to schema `weather`.

Base tables:

- `locations`
- `entsoe_country_aliases`
- `hourly_forecast`

Derived views:

- `latest_hourly_forecast`
- `latest_country_hourly_forecast`
- `price_forecast_weather_features`

`hourly_forecast` stores forecast history per retrieval time, while the main
views expose the latest forecast per location and per mapped country.
`price_forecast_weather_features` maps country-level DWD/Open-Meteo features
to market-area keys such as `DE_LU` for the derived price forecast pipeline.

## Downstream dependencies

Known downstream consumers:

- `Weather Dashboard`
- `Energy Weather Dashboard`
- day-ahead price forecasting post-run pipeline

The energy-weather dashboard uses the country-level view together with ENTSO-E
forecast tables.

## Operational notes

- The crawler creates a hypertable for `hourly_forecast` when TimescaleDB is
  available.
- Default locations are embedded in the crawler, but they can be overridden via
  the `locations` config option.
- `forecast_hours` and `past_hours` control the forecast horizon and historical
  overlap fetched from the API.
