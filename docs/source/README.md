<!--
SPDX-FileCopyrightText: Florian Maurer, Christian Rieke

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Open Energy Data Server (KIT)

This repository builds on the original
[Open Energy Data Server](https://github.com/NOWUM/open-energy-data-server)
and extends it for the workflows documented here.

OEDS-KIT is a crawler-driven data platform for energy-system analysis. It
combines data ingestion, PostgreSQL/TimescaleDB storage, HTTP export through
PostgREST, and dashboarding through Grafana.

![Basic outline of the architecture and included services](media/oeds-architecture.png)

## Core components

### TimescaleDB and PostgreSQL

The main data store is PostgreSQL with TimescaleDB for time-series workloads.
This allows OEDS to handle both large temporal tables and non-time-series
reference data in one system.

### PostGIS

PostGIS is available for schemas that need spatial data or geometry-based
queries.

### Crawlers

Crawler modules under `crawler/` fetch source data and load it into dedicated
schemas such as `entsoe_fms`, `weather`, or `energy_forecast`.

Crawler-specific operational notes live under
[Crawler Documentation](./crawlers/README.md).

## Choose your setup path

Pick the shortest path that matches your goal:

| Goal | Recommended path | Use this when |
| --- | --- | --- |
| Explore the stack locally | `docker compose up -d` | you want PostgreSQL, PgAdmin, PostgREST, and Grafana without scheduled crawlers |
| Run crawlers locally or on a small VM | `docker compose --profile crawlers up -d scheduler crawler-admin` | you want the core stack plus the scheduler and admin UI in containers |
| Install or update a long-lived server reproducibly | `ansible-playbook -i inventory.yml oeds-install-core.yml` or `oeds-install-crawlers.yml` | you want repeatable host preparation, repo rollout, runtime directories, and update playbooks |

If you are unsure, start with the local Compose path and only move to the
deployment playbooks once the crawler scope and operating model are clear.

The public Ansible defaults already point to the GitHub `main` branch. For a
same-host Linux install, `playbooks/inventory.example.yml` is prefilled for
`sudo`, so the minimal path is to copy it to `inventory.yml` and run
`oeds-install-crawlers.yml`.

## Operator quick map

If you are operating a running OEDS-KIT instance, these are the key surfaces:

| Task | Primary surface | Notes |
| --- | --- | --- |
| Inspect dashboards and derived metrics | Grafana | crawler dashboards stay empty until their source schemas are populated |
| Query tables and debug schemas | PgAdmin / SQL | inspect `public.metadata`, crawler schemas, and derived schemas directly |
| Trigger runs, inspect logs, edit schedules | Crawler Admin UI | scheduler control, manual runs, runtime logs, and gapfill operations |
| Edit the source-of-truth config | `CRAWLER_CONFIG.yml` / YAML editor | runtime behavior still comes from YAML, even when edited through the UI |
| Validate post-run quality | Gapfill Tests page and Grafana QA dashboard | synthetic self-tests stay local in admin UI; persisted QA data is written to the gapfill target schema |
| Run derived price forecasts | `entsoe_api:forecast_daily` post-run and `price_forecast` schema | API rows are converted into point, quantile, and backtest outputs; FMS history can bridge warmup |

## Supported crawler functions

The current maintained baseline in this repository covers these data functions:

| Crawler | Source | Auth | Schema | Main outputs | Typical consumers |
| --- | --- | --- | --- | --- | --- |
| `weather_forecast` | Open-Meteo DWD | none | `weather` | hourly forecasts, location views, country views | `Weather Dashboard`, `Energy Weather Dashboard` |
| `entsoe_fms` | ENTSO-E File Library | `ENTSOE_USERNAME`, `ENTSOE_PASSWORD` | `entsoe_fms` | prices, load, generation, outages, transfer capacities, asset lookups | ENTSO-E dashboards, availability map, gapfilling, `Energy Weather Dashboard` |
| `entsoe_api` | ENTSO-E Web API | `ENTSOE_API_KEY` token, separate from FMS login | `entsoe_api` | fresh prices, EXAA sequence, load forecast, wind and solar forecast | `ENTSOE API - Fresh Market Data`, price forecasting inputs |
| `entsog` | ENTSOG transparency API | none | `entsog` | gas operators, points, physical flow, allocation, firm technical capacity | `ENTSOG-Monitor` |
| `smard` | SMARD | none | `smard` | German generation, consumption, and price series | SQL analysis, custom dashboards, SMARD gapfilling |
| `eurostat_crawler` | Eurostat | none | `eurostat` | annual European energy statistics | SQL analysis, country comparison workflows |
| `mastr` | Marktstammdatenregister | none | `mastr` | registry and asset master data | enrichment joins, asset lookups |
| `energy_forecast_crawler` | `energyforecast.de` | `ENERGY_FORECAST_TOKEN` | `energy_forecast` | next-48h quarter-hourly price forecasts | custom dashboards and forecast analysis |
| `epex_spot` | EPEX SPOT SFTP | `EPEX_SFTP_USERNAME`, `EPEX_SFTP_PASSWORD` | `epex_spot` | intraday auctions, trades, indices, and statistics | intraday market analysis and custom dashboards |

For crawler-specific run modes, output tables, and downstream dependencies,
start with [Crawler Documentation](./crawlers/README.md).

## Crawler, schema, and dashboard map

This is the quickest way to understand where data lands and how users normally
see it:

| Crawler | Main schema | Auth | Typical derived output | Main dashboards / consumers |
| --- | --- | --- | --- | --- |
| `weather_forecast` | `weather` | none | country and location forecast views | `Weather Dashboard`, `Energy Weather Dashboard` |
| `entsoe_fms` | `entsoe_fms` | `ENTSOE_USERNAME`, `ENTSOE_PASSWORD` | `entsoe_fms_gapfilled`, availability map objects | ENTSO-E dashboards, `OEDS Gapfilling Quality`, SQL analysis |
| `entsoe_api` | `entsoe_api` | `ENTSOE_API_KEY` token, separate from FMS login | refresh-oriented API tables | `ENTSOE API - Fresh Market Data`, price forecasting inputs |
| `price_forecast` | `price_forecast` | inherited source credentials | point, quantile, and metric tables | `Day-ahead Price Forecast` |
| `entsog` | `entsog` | none | API-backed reporting tables | `ENTSOG-Monitor` |
| `smard` | `smard` | none | optional gapfilled helper tables | SQL analysis, custom dashboards |
| `eurostat_crawler` | `eurostat` | none | annual indicator tables | SQL analysis, comparison workflows |
| `mastr` | `mastr` | none | registry reference tables | asset lookups, enrichment joins |
| `energy_forecast_crawler` | `energy_forecast` | `ENERGY_FORECAST_TOKEN` | forecast tables for next 48h | custom forecast dashboards and analysis |
| `epex_spot` | `epex_spot` | `EPEX_SFTP_USERNAME`, `EPEX_SFTP_PASSWORD` | intraday market tables | intraday analysis and custom dashboards |

## How to access the data

Once the stack is running, there are four main ways to inspect or use the data:

| Access path | What you get | How to use it |
| --- | --- | --- |
| Grafana | ready-made dashboards and exploratory charts | open `http://localhost:3006/` and use the provisioned dashboards |
| PgAdmin / SQL | direct schema, table, and query access | open `http://localhost:8080/` and query PostgreSQL directly |
| PostgREST | HTTP access to tables, views, and database objects | call `http://localhost:3001/` from scripts, notebooks, or services |
| Python / notebooks | programmatic access and custom analysis | run `uv run python ...` and use the example scripts under `examples/` or `scripts/` |

The Crawler Admin UI at `http://localhost:3010/admin` is the operational
surface for schedules, manual runs, YAML editing, logs, run history, and
productive gapfill settings. It is not the primary data browser, but it is the
fastest way to see which crawlers exist, which ones are enabled, and whether
recent runs succeeded.

If you want to know where a specific dataset ends up:

- check the crawler page under [Crawler Documentation](./crawlers/README.md)
- inspect the crawler section in `CRAWLER_CONFIG.yml`
- query `public.metadata` in PostgreSQL after the first successful crawler run

## Data sources and licensing

OEDS itself is open-source infrastructure, but the crawled datasets do not all
share the same access model.

In this repository you will find:

- fully open public sources
- sources that require user credentials or approved accounts
- proprietary APIs that can be integrated technically but not redistributed by default

For production and publication scenarios, document each crawler's source,
authentication model, and declared license on its crawler page. The deployment
operator remains responsible for complying with upstream terms of use.

## Contributing

When adding a new crawler:

1. create a module in `crawler/`
2. add its scheduler entry to `CRAWLER_CONFIG.yml`
3. document it under `docs/source/crawlers/`
4. add any required bootstrap SQL to `docker/initdb/10-init.sql` if fresh installs need it

## Repository lineage

This repository is a KIT-maintained derivative of the Open Energy Data Server
project. The maintained tree keeps the upstream lineage visible through Git
history, SPDX metadata, and the upstream link above, while legacy assets outside
the current KIT deployment path are intentionally omitted.

## Notable crawler-backed dashboards

- `Weather Dashboard`
- `Energy Weather Dashboard`
- `ENTSOE Transfer Capacity, Adequacy & Projects`

These dashboards are provisioned from `data/provisioning/grafana/dashboards/`,
grouped by crawler subfolder plus `shared/`,
and depend on their related crawler schemas being populated.

## Troubleshooting

For common operator problems such as empty Grafana panels, missing crawler
credentials, or PostgreSQL major-version upgrades, see
[Troubleshooting](./troubleshooting.md).
