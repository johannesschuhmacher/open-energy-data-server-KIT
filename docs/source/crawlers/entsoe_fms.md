# entsoe_fms

## Purpose

`crawler.entsoe_fms` imports selected extracts from the ENTSO-E Transparency Platform File Library (FMS) into the `entsoe_fms` schema.

It is the main source for:

- market data such as day-ahead prices
- load and generation forecasts
- installed generation capacity snapshots
- outage and unavailability data
- static auxiliary lookup tables used by downstream views and dashboards

## Source system and authentication

The crawler reads ENTSO-E FMS CSV extracts over HTTPS with OAuth2 password grant.

Required credentials:

- `ENTSOE_USERNAME`
- `ENTSOE_PASSWORD`

They can be provided as environment variables or via a local `.env` file loaded by the crawler.

## Manual execution

Run the crawler from the repository root:

```shell
python -m crawler.entsoe_fms
```

The initial run can be large because the crawler starts from historical files and incrementally builds the target tables. For production-like environments, it is recommended to run the crawler manually once before enabling the scheduler.

## Scheduler configuration

The crawler is configured under the `entsoe_fms` key in `CRAWLER_CONFIG.yml`.

Common options are documented in [crawler_config.md](../crawler_config.md).

Important options used by this crawler:

- `schema_name`
- `database_uri`
- `schedule`
- `default_start_date`
- `post_run_scripts`
- `gapfill`
- `target_data_items`

`default_start_date` controls the first historical window for a fresh schema. If the
target tables do not exist yet, the crawler starts from this date. Once data is
present, the crawler switches to its incremental update behavior automatically.

`target_data_items` is optional. If it is set, the crawler only processes the named FMS data items. This is useful for partial runs and maintenance tasks.

Example:

```yaml
entsoe_fms:
  enable: false
  schema_name: "entsoe_fms"
  schedule: "0 * * * *"
  default_start_date: "2026-01-01"
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
  target_data_items:
    - "DayAheadTotalLoadForecast_6.1.B_r3"
    - "GenerationForecastsForWindAndSolar_14.1.D_r3"
```

Recommended first-run workflow on a clean deployment:

1. Keep `enable: false`.
2. Set `default_start_date` to the narrowest window you actually need.
3. Optionally limit `target_data_items` for a staged initial load.
4. Add `ENTSOE_USERNAME` and `ENTSOE_PASSWORD` to `crawler/.env`.
5. Enable the crawler only after these values are in place.

## Post-run processing

`entsoe_fms` currently has two post-run scripts:

1. `scripts/gapfill_timeseries.py`
2. `scripts/refresh_entsoe_availability_map.py`

They run only after the crawler itself finishes successfully. The order is
intentional: gapfilled time-series copies are produced first, then the
availability-map objects are refreshed.

### Time-series gapfilling

`scripts/gapfill_timeseries.py` reads the `gapfill` block from the
`entsoe_fms` config. It uses the same `database_uri` as the crawler and resolves
Docker host and port overrides through `OEDS_DB_HOST` and `OEDS_DB_PORT`.

The script writes to a separate target schema, by default
`entsoe_fms_gapfilled`. Raw `entsoe_fms` tables are never modified.

The configured tables are regular time-series tables where missing values or
missing timestamps can be filled safely within bounded gaps:

- `ActualTotalLoad`
- `DayAheadTotalLoadForecast`
- `GenerationForecastsForWindAndSolar`
- `EnergyPrices`
- `ForecastedTransferCapacities`
- `PhysicalFlows`

Each target table keeps the source columns and adds gapfill metadata columns:

- `gapfill_run_id`
- `gapfill_method`
- `gapfill_created_row`
- `gapfill_filled_columns`
- `gapfill_updated_at`

The script also maintains control tables in `entsoe_fms_gapfilled`:

- `gapfill_runs`: one row per gapfill execution
- `gapfill_metrics`: per-table, per-value-column, per-group quality metrics
- `gapfill_tracking`: incremental state per source table
- `gapfill_test_results`: synthetic self-test status for dashboards
- `gapfill_test_series`: synthetic source and gapfilled series for dashboards

Tracking uses source timestamps and, when available, `UpdateTime(UTC)`. This is
important for ENTSO-E FMS because historical records can be revised after their
original `DateTime(UTC)`.

The default method is `donor_refined`. It searches complete donor windows using
the configured seasonal periods, compares the surrounding context and boundary
continuity, copies the best matching segment, and smooths the segment edges to
avoid visible jumps. With the default `candidate_periods` of `24h` and `7d`,
the filler can choose between daily and weekly patterns instead of always using
the previous day. `max_gap_periods` prevents large outages from being filled
silently. The configured `lookback` matches the donor search radius so
incremental runs read enough history for weekly donor candidates. Manual runs
can use:

```shell
uv run python scripts/gapfill_timeseries.py --job entsoe_fms
uv run python scripts/gapfill_timeseries.py --job entsoe_fms --dry-run
uv run python scripts/gapfill_timeseries.py --job entsoe_fms --self-test
```

The Grafana dashboard `OEDS Gapfilling Quality` displays the latest run,
per-table fill metrics, and the synthetic self-test series.

### Availability map refresh

`scripts/refresh_entsoe_availability_map.py` refreshes SQL objects used by the
ENTSO-E availability map dashboards. It reads the same crawler config, builds a
database connection for the `entsoe_fms` schema, and executes
`scripts/lib/entsoe_availability_map.sql`.

This script is separate from gapfilling because the availability map is a
domain-specific derived dataset rather than a generic time-series quality task.

## Active data items and target tables

The crawler currently maps the following active FMS items to PostgreSQL tables:

- `AggregatedFillingRateOfWaterReservoirsAndHydroStoragePlants_16.1.D_r3` -> `AggregatedFillingRateOfWaterReservoirsAndHydroStoragePlants`
- `ActualTotalLoad_6.1.A_r3` -> `ActualTotalLoad`
- `DayAheadTotalLoadForecast_6.1.B_r3` -> `DayAheadTotalLoadForecast`
- `ActualGenerationOutputPerGenerationUnit_16.1.A_r3` -> `ActualGenerationOutputPerGenerationUnit`
- `AggregatedGenerationPerType_16.1.B_C_r3` -> `AggregatedGenerationPerType`
- `CommercialSchedulesNetPositions_12.1.F_r3` -> `CommercialSchedulesNetPositions`
- `DayAheadAggregatedGeneration_14.1.C_r3` -> `DayAheadAggregatedGeneration`
- `GenerationForecastsForWindAndSolar_14.1.D_r3` -> `GenerationForecastsForWindAndSolar`
- `EnergyPrices_12.1.D_r3` -> `EnergyPrices`
- `ExpansionAndDismantlingProjects_9.1_r3` -> `ExpansionAndDismantlingProjects`
- `ForecastedTransferCapacities_11.1_r3` -> `ForecastedTransferCapacities`
- `InstalledGenerationCapacityPerProductionUnit_14.1.B_r3` -> `InstalledGenerationCapacityPerProductionUnit`
- `InstalledGenerationCapacityAggregated_14.1.A_r3` -> `InstalledGenerationCapacityAggregated`
- `PhysicalFlows_12.1.G_r3` -> `PhysicalFlows`
- `ProductionAndGenerationUnits_r3` -> `ProductionAndGenerationUnits`
- `TotalCapacityAlreadyAllocated_12.1.C_r3` -> `TotalCapacityAlreadyAllocated`
- `TotalCapacityNominated_12.1.B_r3` -> `TotalCapacityNominated`
- `TotalLoadForecast_6.1.C_D_E_r3` -> `TotalLoadForecast`
- `TransmissionAssets_r3` -> `TransmissionAssets`
- `UnavailabilityInTheTransmissionGrid_10.1.A_B_r3` -> `UnavailabilityInTheTransmissionGrid`
- `UnavailabilityOfConsumptionUnits_7.1.A_B_r3` -> `UnavailabilityOfConsumptionUnits`
- `UnavailabilityOfOffshoreGrid_10.1.C_r3` -> `UnavailabilityOfOffshoreGrid`
- `UnavailabilityOfProductionAndGenerationUnits_15.1.A_B_C_D_r3` -> `UnavailabilityOfProductionAndGenerationUnits`
- `UseOfTransferCapacity_12.1.A_r3` -> `UseOfTransferCapacity`
- `YearAheadForecastMargin_8.1_r3` -> `YearAheadForecastMargin`

In addition, the crawler writes and refreshes:

- `areas`
- `psrtype`
- `powersystemdata`

## Output schema

The crawler writes to schema `entsoe_fms`.

The tables fall into four groups:

- operational time series
- forecasts
- installed capacity snapshots
- outage and availability related tables

This schema is consumed directly by Grafana dashboards and by downstream SQL
objects such as the live availability map described in
[examples/entsoe_live_availability_map.md](../examples/entsoe_live_availability_map.md).

## Downstream dependencies

Known downstream consumers include:

- `Energy Weather Dashboard`
  Uses `DayAheadTotalLoadForecast`, `GenerationForecastsForWindAndSolar`, and `EnergyPrices`.
- `ENTSOE Transfer Capacity, Adequacy & Projects`
  Uses `UseOfTransferCapacity`, `YearAheadForecastMargin`, and `ExpansionAndDismantlingProjects`.
- ENTSO-E availability map SQL and dashboards
  Uses `UnavailabilityOfProductionAndGenerationUnits`, `InstalledGenerationCapacityPerProductionUnit`, and `powersystemdata`.
- ENTSO-E dashboards under `data/provisioning/grafana/dashboards/`

If one of these tables is missing or empty, the related panels will either be empty or fail depending on the query.

## Historical maintenance and partial runs

The repository contains `scripts/backfill_entsoe_unavailability.py` for
targeted outage backfills.

The crawler itself also contains a `backwards_update(...)` helper for historical file reprocessing. This is intended for maintenance work rather than normal scheduled execution.

## Operational notes

- The first full run is expensive and can take a long time.
- On a fresh install, the default repository config keeps the crawler disabled so
  the initial backfill window can be reviewed before the first scheduler run.
- Incremental behavior is driven by existing table state and `UpdateTime` columns.
- Some FMS items are treated as special cases:
  - single-file extracts such as installed capacity, production units, and transmission assets
  - annual archive-style files such as aggregated hydro storage filling rates
  - full-upsert asset and outage tables where revisions are expected
- If you add a new FMS extract, update the active item-to-table mapping in the crawler and document it here at the same time.
