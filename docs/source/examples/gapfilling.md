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
    method: "donor_refined"
    candidate_periods: ["24h", "7d"]
    donor_context_periods: 6
    donor_search_radius: "28d"
    refinement_periods: 3
    max_gap_periods: 24
    lookback: "28d"
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

- `donor_refined`: find a complete donor window with matching context,
  seasonality, and edge continuity, then smooth the imputed segment at both
  boundaries
- `donor_match`: copy the best matching donor window without the edge
  refinement step
- `linear`: time-based linear interpolation inside bounded gaps
- `previous_period`: copy from the previous configured period, then fall back to
  linear interpolation
- `seasonal_linear`: blend previous-period and linear candidates where both are
  available

`donor_refined` is the recommended default for ENTSO-E time series because it
can choose between daily and weekly seasonal candidates instead of always
copying exactly one fixed period. `max_gap_periods` prevents large outages from
being filled silently. Keep `lookback` at least as large as
`donor_search_radius`; otherwise incremental post-run executions may not read
enough historical rows for weekly donor matching.

## Advanced quality ideas

The production path now implements contextual donor matching and edge
refinement behind the OEDS interface: crawler config, separate target schema,
idempotent writes, run metrics, dashboard data, and tests.

Linear-interpolation artefact detection is deliberately not enabled as a
destructive default. It can produce false positives on real ramp-like energy
time series. If this is needed later, it should first be added as an audit
metric that reports suspicious linear ranges before any raw-looking values are
converted to gaps.
