# Deployment Validation

This document captures the currently verified deployment and operation path for
OEDS after the container, playbook, and admin-runtime adjustments from
May 1, 2026.

## Tested target

The validation was executed against a clean external Linux VM using the
containerized Level-3 installation path:

1. `oeds-uninstall.yml` for a full test reset
2. `oeds-install-crawlers.yml` for the core stack plus crawler services
3. `oeds-smoke-test.yml` for post-install health checks

The target stack included:

- PostgreSQL / TimescaleDB
- PgAdmin
- PostgREST
- Grafana
- `scheduler`
- `crawler-admin`
- optional Portainer during the VM validation run

## Adjustments made during validation

The deployment path and runtime behavior were aligned to what the VM test
actually required:

- crawler secrets are now supplied to the crawler containers via Compose
  `env_file` instead of mounting `crawler/.env` into the container filesystem
- the containerized admin UI runs with write access to the mounted
  `CRAWLER_CONFIG.yml` so schedule edits and YAML saves persist on the host
- admin config writes now fall back cleanly when Docker bind-mounted single
  files reject atomic `rename` replacement
- admin log handling no longer throws follow-up errors when a finished run has
  already closed its file handle
- playbooks now honor `oeds_repo_url`, `oeds_repo_version`, `oeds_root`,
  `oeds_runtime_dir`, and related overrides consistently
- smoke tests retry HTTP checks so fresh Grafana and PgAdmin startups do not
  fail prematurely

## Verified functions

The following paths were exercised successfully on the running VM:

- core service startup and health checks for PostgreSQL, PgAdmin, PostgREST,
  Grafana, scheduler, and crawler admin
- optional Portainer startup and login bootstrap timing behavior
- Grafana dashboard provisioning
- PostgREST root endpoint and `public.metadata` access
- crawler admin health endpoint, dashboard, YAML editor, and crawler detail
  pages
- YAML validation and save through the admin UI
- scheduler schedule edits and revert through the admin UI
- scheduler reload behavior after config changes
- manual crawler execution through the admin UI, including run history and log
  retrieval
- first `weather_forecast` run creating and populating the `weather` schema and
  `public.metadata` entries on a clean install

## Observed results on May 1, 2026

The validated VM reported these concrete outcomes after the fixes:

- Grafana health `ok` with 26 provisioned dashboards visible through the API
- PgAdmin responding with the expected login redirect
- PostgREST serving the OpenAPI root document and `public.metadata`
- admin YAML save returning HTTP `303` after the write-path fix
- scheduler save and revert returning HTTP `303`
- a manual `weather_forecast` run finishing with status `succeeded` and log
  retrieval through the admin UI
- the `weather` schema present with populated forecast tables after the first
  manual run
- `public.metadata` containing the expected `weather` dataset entry

## Clean-install behavior

The tested clean setup behaves as follows:

- the core stack is available immediately after `docker compose up -d`
- the optional crawler profile starts successfully after crawler runtime files
  are present
- dashboards that depend on crawler data stay empty until the corresponding
  crawler has run at least once
- authenticated crawlers such as `entsoe_fms`, `energy_forecast_crawler`, and
  `epex_spot` still require secrets in `crawler/.env`
- `entsoe_fms` should have its `default_start_date` reviewed before the first
  enabled run if a full historical backfill is not desired

## Recommended post-install checks

After a fresh install, use this sequence:

1. run the smoke test playbook
2. open Grafana, PgAdmin, PostgREST, and the admin UI once
3. run `weather_forecast` manually before assuming crawler-backed dashboards or
   schemas are ready
4. enable additional crawlers only after their secrets and initial backfill
   scope have been reviewed

## Known remaining limits

The validation did not treat every upstream source as executable on the test
VM:

- source-specific runs that require real credentials were not force-enabled
  without operator secrets
- a non-blocking Timescale startup warning for `timescaledb_toolkit` was still
  visible during initial database setup, but it did not break the tested stack

The raw command logs from the external VM validation are kept as local operator
artifacts under `playbooks/run_logs/` and are not part of the published
repository contract.
