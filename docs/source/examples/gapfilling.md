# OEDS Time-Series Gapfilling

OEDS includes a generic post-run gapfiller for regular time-series tables. The
first configured job targets selected `entsoe_fms` tables and writes cleaned
copies to `entsoe_fms_gapfilled`.

The source tables are never modified. Each gapfilled target table keeps the
source columns and adds:

- `gapfill_run_id`
- `gapfill_method`
- `gapfill_created_row`
- `gapfill_filled_columns`
- `gapfill_updated_at`

Run metadata is written to:

- `entsoe_fms_gapfilled.gapfill_runs`
- `entsoe_fms_gapfilled.gapfill_metrics`
- `entsoe_fms_gapfilled.gapfill_tracking`
- `entsoe_fms_gapfilled.gapfill_test_results`
- `entsoe_fms_gapfilled.gapfill_test_series`

## Manual run

```shell
uv run python scripts/gapfill_timeseries.py --job entsoe_fms
```

The script reads `CRAWLER_CONFIG.yml`, uses the crawler database URI, and
respects Docker host/port overrides through `OEDS_DB_HOST` and `OEDS_DB_PORT`.

## Self-test data for the dashboard

```shell
uv run python scripts/gapfill_timeseries.py --job entsoe_fms --self-test
```

This writes synthetic test results and sample time series to the gapfill target
schema. The Grafana dashboard `OEDS Gapfilling Quality` displays both the latest
real gapfill run and these self-test results.

## Configuration

The ENTSO-E FMS crawler config contains a `gapfill` block:

```yaml
entsoe_fms:
  post_run_scripts:
    - "scripts/gapfill_timeseries.py"
    - "scripts/refresh_entsoe_availability_map.py"
  gapfill:
    enable: true
    target_schema: "entsoe_fms_gapfilled"
    method: "linear"
    max_gap_periods: 24
    lookback: "7d"
    fail_on_table_error: true
    tables:
      - "ActualTotalLoad"
      - "DayAheadTotalLoadForecast"
      - "GenerationForecastsForWindAndSolar"
      - "EnergyPrices"
      - "ForecastedTransferCapacities"
      - "PhysicalFlows"
```

Available methods are:

- `linear`: time-based linear interpolation inside bounded gaps
- `previous_period`: copy from the previous configured period, then fall back to
  linear interpolation
- `seasonal_linear`: blend previous-period and linear candidates where both are
  available

`max_gap_periods` prevents large outages from being filled silently.

## Advanced quality ideas

The current OEDS implementation focuses on deterministic, auditable gapfilling
for operational post-run use. A separate prototype explored a broader
three-stage quality pipeline:

1. Detect linear interpolation artefacts with rolling R2 scores and convert
   confirmed artefact ranges back to missing values.
2. Fill missing values with contextual donor matching or probabilistic seasonal
   methods.
3. Refine imputed segments by checking edge jumps, variance, autocorrelation,
   and distribution differences.

Those ideas are useful future extensions, but they should be added behind the
same OEDS interface used here: crawler config, separate target schema,
idempotent writes, run metrics, and tests. The prototype's separate `.env`
handling, hard-coded schema paths, and per-value-column append workflow are not
used in the production post-run path.
