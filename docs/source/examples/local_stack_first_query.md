# Local Stack To First Query

This walkthrough is the shortest reproducible path from clone to a useful OEDS
result.

## Goal

Bring up the local stack, run one crawler manually, and verify the resulting
data through SQL and HTTP access.

## Steps

1. Start the local services from the repository root:

   ```bash
   docker compose up -d
   ```

2. Sync the Python environment:

   ```bash
   uv sync --locked
   ```

3. Run one crawler manually:

   ```bash
   uv run python -m crawler.weather_forecast
   ```

4. Verify that crawler-owned tables exist:

   ```bash
   docker exec -it open-data psql -U opendata -d opendata -c "\dt weather.*"
   ```

5. Query one result row through PostgREST:

   ```bash
   curl "http://localhost:3001/weather_forecast?limit=1"
   ```

## What this proves

- the Compose stack is healthy
- Python crawler execution works against the local database
- PostgREST sees the newly populated schema
- the repository is in a state where documentation and code examples match

## Useful follow-ups

- open Grafana at `http://localhost:3006/`
- inspect the crawler in the admin UI at `http://localhost:3010/admin`
- continue with [First crawler change](first_crawler_change.md)
