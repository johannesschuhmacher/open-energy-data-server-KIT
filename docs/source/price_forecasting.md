# Day-ahead price forecasting

OEDS includes an optional derived day-ahead price forecast pipeline. It is
implemented as a post-run script and writes model output to a separate
`price_forecast` schema, keeping source crawler schemas immutable.

## Source data

The first implementation uses these inputs when available:

- `entsoe_api.day_ahead_prices` for fresh SDAC and EXAA prices
- `entsoe_fms."EnergyPrices"` as historical fallback and training source
- `entsoe_api.load_forecasts` and
  `entsoe_fms."DayAheadTotalLoadForecast"` for load forecasts
- `entsoe_api.wind_solar_forecasts` and
  `entsoe_fms."GenerationForecastsForWindAndSolar"` for renewable forecasts
- `weather.price_forecast_weather_features` for DWD/Open-Meteo weather proxies

The weather feature view is created by `weather_forecast` and exposes country
aggregates under market-area-style keys such as `DE_LU`.

## Model backends

The default backend is `auto`.

When the upstream `da_price_forecasting` package is importable, OEDS uses the
upstream LEAR implementation for the point forecast:

- `da_price_forecasting.features.engineering.build_price_features`
- `da_price_forecasting.features.engineering.build_load_features`
- `da_price_forecasting.features.engineering.build_temporal_features`
- `da_price_forecasting.features.engineering.build_y_matrix`
- `da_price_forecasting.models.lear.rolling_point_forecast`

If the upstream package or its optional ML dependencies are not available, OEDS
falls back to its local ridge-regression baseline. Both backends write to the
same `price_forecast` schema.

The model uses:

- EXAA prices for the target delivery interval
- lagged day-ahead prices from 1, 2, and 7 days before delivery
- calendar features
- load, wind, solar, and weather proxy covariates when present

SQRA is not wired into the post-run path yet because it depends on `remodels`.
The current quantile rows are produced from empirical residual offsets around
the point forecast and are a bridge until the SQRA environment is integrated.

## Upstream package setup

The deployment path installs the upstream
`DA_Price_Forecasting_Pipeline_DE_LU` package from the pinned commit in the
OEDS `price-forecast` dependency group. The adapter still accepts a local
checkout override for development:

```shell
set DA_PRICE_FORECASTING_REPO_PATH=C:\path\to\DA_Price_Forecasting_Pipeline_DE_LU
set OEDS_PRICE_FORECAST_BACKEND=auto
```

The optional OEDS dependency group contains the upstream LEAR runtime
dependencies that are not part of the crawler baseline:

```shell
uv sync --locked --group price-forecast
```

On this Windows checkout `uv` may need to be upgraded first because the project
requires `uv >=0.11.7,<0.12`.

The crawler Docker image also installs this group, so the scheduler can use the
upstream LEAR backend without mounting a separate checkout.

## Deployment settings

The containerized scheduler reads these optional environment variables:

- `OEDS_PRICE_FORECAST_BACKEND`, default `auto`
- `OEDS_PRICE_FORECAST_MARKET_AREA`, default `DE_LU`
- `OEDS_PRICE_FORECAST_TRAIN_DAYS`, default `56`
- `OEDS_PRICE_FORECAST_BACKTEST_DAYS`, default `2` in Compose
- `OEDS_PRICE_FORECAST_RETENTION_DAYS`, default `180`
- `OEDS_PRICE_FORECAST_UPSTREAM_VARIANT`, default `exaa_only`

Repeated productive runs keep the newest completed run as the active forecast
and mark older completed runs for the same market area, target date, and variant
as `superseded`. Rows older than the retention window are deleted from
`price_forecast.forecast_runs`; dependent point, quantile, and metric rows are
removed through cascading foreign keys.

## Training data

The productive forecast is API-first, but training uses the historical rows
already stored in OEDS. With `OEDS_PRICE_FORECAST_TRAIN_DAYS=56`, the loader
reads roughly 70 market days because the model also needs lagged features. On a
fresh API-only deployment, run or temporarily enable
`entsoe_api:training_bootstrap` once so the `entsoe_api` tables contain at least
90 days of prices, EXAA prices, load forecasts, and renewable forecasts. After
that warmup, the daily API job keeps the rolling training window current.

Before every forecast, the loader checks API coverage for the required SDAC and
EXAA training window. If API coverage is high enough, API rows are preferred for
training and fresh intervals. If API coverage is still too short, FMS rows are
used for the historical training window and API rows are still used for fresh
target-day inputs where they are available. This keeps the forecast runnable
during API warmup while moving to API-only training automatically once enough
history has accumulated.

## Running manually

Run a deterministic self-test without PostgreSQL:

```shell
python scripts/run_price_forecast.py --self-test --backtest-days 3
```

Force the upstream backend:

```shell
python scripts/run_price_forecast.py --self-test --model-backend upstream --upstream-repo-path C:\path\to\DA_Price_Forecasting_Pipeline_DE_LU
```

Run against the OEDS database:

```shell
python scripts/run_price_forecast.py --target-date 2026-05-19 --backtest-days 7
```

Without `--target-date`, the script forecasts tomorrow in the Europe/Berlin
market day.

## Scheduler integration

`entsoe_api` is the productive forecast trigger. It refreshes the ENTSO-E Web
API data and then runs the forecast post-run script:

```yaml
entsoe_api:
  jobs:
    forecast_daily:
      schedule: "35 11 * * *"
      post_run_scripts:
        - "scripts/run_price_forecast.py"
```

The Web API token is different from the FMS login. Enable this crawler only when
`ENTSOE_API_KEY`, `ENTSOE_SECURITY_TOKEN`, or `ENTSOE_API` is available.

The same crawler also contains a disabled warmup job:

```yaml
entsoe_api:
  jobs:
    training_bootstrap:
      enable: false
      lookback_days: 120
      run_post_scripts: false
```

Use it manually or enable it once on a clean deployment to populate enough
training history before the first productive forecast.

The intended operational sequence is:

1. refresh the API price inputs shortly after EXAA prices are available
2. run `scripts/run_price_forecast.py`
3. write derived point and quantile forecasts to `price_forecast`
4. run optional backtests or metric refreshes after actual prices are available

## Output schema

The script creates these tables:

- `price_forecast.forecast_runs`
- `price_forecast.point_forecasts`
- `price_forecast.quantile_forecasts`
- `price_forecast.metrics`

Runs with insufficient training data are recorded as `skipped` and exit
successfully by default, which keeps post-run execution idempotent during early
deployments.

## Dashboard

Grafana provisions `Day-ahead Price Forecast` from
`data/provisioning/grafana/dashboards/price_forecast/`. The dashboard shows the
latest point forecast, selected quantiles, recent runs, and backtest metrics.
