# Gapfill QA Walkthrough

This walkthrough demonstrates one of the stronger OEDS features: gapfill logic
with synthetic QA and holdout validation.

## Goal

Run the built-in gapfill QA path without relying on external source systems.

## Steps

1. Start the local stack and sync the Python environment:

   ```bash
   docker compose up -d
   uv sync --locked
   ```

2. Start the admin UI if it is not already running:

   ```bash
   uv run python crawler_admin_server.py
   ```

3. Open the gapfill QA page:

   - `http://127.0.0.1:3010/admin/gapfill`

4. Run one synthetic self-test from the UI, for example:

   - `missing_timestamp_gap`
   - `donor_refined_seasonal_gap`

5. Repeat the same validation on the CLI:

   ```bash
   uv run python scripts/gapfill_timeseries.py --job entsoe_fms --self-test
   ```

## What to inspect

- expected vs. actual filled point counts
- MAE and RMSE for holdout tests
- chart markers for imputed points
- whether the same logic is reachable from UI and CLI

## Why this example matters

This is a good public example because it demonstrates reusable domain logic,
operator tooling, and testability without needing live upstream credentials.
