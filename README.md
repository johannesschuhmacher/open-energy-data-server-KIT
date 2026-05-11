<!-- SPDX-FileCopyrightText: Florian Maurer, Christian Rieke, Andre Meyer, Haoshen Zhang, Johannes Schuhmacher -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Open Energy Data Server

This repository builds on the original
[Open Energy Data Server](https://github.com/NOWUM/open-energy-data-server)
and extends it for the workflows documented here.

Open Energy Data Server (OEDS) is a crawler-driven data platform for
energy-system analysis. It combines data ingestion, PostgreSQL/TimescaleDB,
PostgREST, and Grafana into one reusable stack for collecting, storing, and
serving energy data.

Documentation lives in `docs/source/` and can be built locally with Sphinx.
The repository already ships a `.readthedocs.yaml` for the future public
Read the Docs project, but this README intentionally does not link to the old
unrelated RTD instance.

![OEDS architecture overview](docs/source/media/oeds-architecture.png)

## What OEDS includes

- crawler modules for public and semi-public energy datasets
- PostgreSQL with TimescaleDB for time-series storage
- PostGIS for spatial extensions
- PostgREST for HTTP access to database objects
- provisioned Grafana dashboards

Typical source areas already covered in the repository include:

- ENTSO-E Transparency Platform File Library
- weather forecasts via Open-Meteo DWD
- SMARD
- Eurostat
- Energy Forecast price forecasts

## Source access model

OEDS combines sources with different access and licensing models:

- open public sources such as SMARD, Eurostat, or weather APIs
- credentialed or semi-public sources such as ENTSO-E FMS
- proprietary APIs such as `energyforecast.de`

That means a successful deployment depends not only on OEDS itself, but also on
your rights to access, store, and republish the upstream data. Always review
source-specific terms, rate limits, and license conditions before enabling a
crawler in a public environment.

## Choose your setup path

Pick the shortest path that matches your goal:

| Goal | Recommended path | Use this when |
| --- | --- | --- |
| Explore the stack locally | `docker compose up -d` | you want PostgreSQL, PgAdmin, PostgREST, and Grafana without scheduled crawlers |
| Run crawlers locally or on a small VM | `docker compose --profile crawlers up -d scheduler crawler-admin` | you want the core stack plus the scheduler and admin UI in containers |
| Install or update a long-lived server reproducibly | `ansible-playbook -i inventory.yml oeds-install-core.yml` or `oeds-install-crawlers.yml` | you want repeatable host preparation, repo rollout, runtime directories, and update playbooks |

If you are unsure, start with the local Compose path and only move to the
Ansible playbooks once the stack and crawler scope are clear.

## Supported crawler functions

The current maintained baseline in this repository covers these data functions:

| Crawler | Source | Auth | Schema | Main outputs | Typical consumers |
| --- | --- | --- | --- | --- | --- |
| `weather_forecast` | Open-Meteo DWD | none | `weather` | hourly forecasts, location views, country views | `Weather Dashboard`, `Energy Weather Dashboard` |
| `entsoe_fms` | ENTSO-E File Library | `ENTSOE_USERNAME`, `ENTSOE_PASSWORD` | `entsoe_fms` | prices, load, generation, outages, transfer capacities, asset lookups | ENTSO-E dashboards, availability map, gapfilling, `Energy Weather Dashboard` |
| `entsog` | ENTSOG transparency API | none | `entsog` | gas operators, points, physical flow, allocation, firm technical capacity | `ENTSOG-Monitor` |
| `smard` | SMARD | none | `smard` | German generation, consumption, and price series | SQL analysis, custom dashboards, SMARD gapfilling |
| `eurostat_crawler` | Eurostat | none | `eurostat` | annual European energy statistics | SQL analysis, country comparison workflows |
| `mastr` | Marktstammdatenregister | none | `mastr` | registry and asset master data | enrichment joins, asset lookups |
| `energy_forecast_crawler` | `energyforecast.de` | `ENERGY_FORECAST_TOKEN` | `energy_forecast` | next-48h quarter-hourly price forecasts | custom dashboards and forecast analysis |
| `epex_spot` | EPEX SPOT SFTP | `EPEX_SFTP_USERNAME`, `EPEX_SFTP_PASSWORD` | `epex_spot` | intraday auctions, trades, indices, and statistics | intraday market analysis and custom dashboards |

For crawler-specific configuration, run modes, output tables, and downstream
dependencies, start with [Crawler Documentation](docs/source/crawlers/README.md).

## Quick start

Start the local services from the repository root:

```bash
docker compose up -d
```

If you already have a populated PostgreSQL/TimescaleDB data directory from an
older major version, do not switch the image tags in place. Moving to
PostgreSQL 18 requires a database migration such as `pg_upgrade` or
dump/restore.

This starts the standard local development stack:

- PostgreSQL / TimescaleDB on `localhost:6432`
- PgAdmin on `http://localhost:8080/`
- PostgREST on `http://localhost:3001/`
- Grafana on `http://localhost:3006/`

If one of these ports is already occupied, override it with an environment
variable such as `OEDS_POSTGRES_PORT=16432`.

Optional crawler services are available through the `crawlers` profile:

```bash
docker compose --profile crawlers up -d scheduler crawler-admin
```

This builds a shared Python image and starts:

- the scheduler as `python crawler_scheduler.py`
- the admin UI as `python crawler_admin_server.py`

Additional crawler-service access:

- Crawler Admin UI on `http://localhost:3010/admin`

Portainer is no longer part of the default core stack. If you want the optional
container-management UI, start the `ops` profile explicitly:

```bash
docker compose --profile ops up -d portainer portainer_agent
```

The Portainer documentation requires the first admin setup to finish within a
few minutes after the first startup. If you do not need a separate container UI,
the Docker CLI remains the primary operations path for OEDS.

The crawler containers keep these runtime paths writable and persistent across
restarts:

- `CRAWLER_CONFIG.yml`
- `crawler/.env` as a Compose `env_file`
- `crawler/data/`
- `logs/`

The admin UI also persists its run history and log metadata in
`crawler_admin_state/`. In the container profile it has write access to the
mounted `CRAWLER_CONFIG.yml` so scheduler edits and YAML saves survive
rebuilds.

For host deployments you can point these runtime paths at a separate directory
by setting `OEDS_RUNTIME_DIR` before running Compose.

For a reproducible host install through Ansible, the public defaults already
point to the GitHub `main` branch:

```bash
cd playbooks
cp inventory.example.yml inventory.yml
ansible-playbook -i inventory.yml oeds-install-crawlers.yml
```

The example inventory is prefilled for a same-host Linux install with `sudo`.
For a remote host, replace the `localhost` entry with `ansible_host` and, when
needed, `ansible_user`. The full deployment workflow is documented in
[`playbooks/README.md`](playbooks/README.md).

Sync the Python environment:

```bash
uv sync --locked
```

For host-side crawler execution, this environment includes native dependencies
such as `pygrib` and therefore expects an available `ecCodes` toolchain. On
Windows, Docker or WSL is usually the simpler path.

For crawler-specific credentials, create `crawler/.env` from
`crawler/.env.example`.

Run a crawler manually:

```bash
uv run python -m crawler.weather_forecast
uv run python -m crawler.entsoe_fms
uv run python -m crawler.energy_forecast_crawler
```

Run the scheduler:

```bash
uv run python crawler_scheduler.py
```

Run the admin UI:

```bash
uv run python crawler_admin_server.py
```

`uv` creates the local `.venv/`, respects `.python-version`, and both entry
points still load `crawler/.env` automatically when the file exists.

## How to access the data

Once the stack is running, there are four main ways to inspect or use the data:

| Access path | What you get | How to use it |
| --- | --- | --- |
| Grafana | ready-made dashboards and exploratory charts | open `http://localhost:3006/` and use the provisioned dashboards under `data/provisioning/grafana/dashboards/` |
| PgAdmin / SQL | direct schema, table, and query access | open `http://localhost:8080/` and connect to PostgreSQL for ad-hoc SQL |
| PostgREST | HTTP access to tables, views, and RPC-style database objects | call `http://localhost:3001/` from scripts, notebooks, or external services |
| Python / notebooks | programmatic access and custom analysis | run `uv run python ...` against the local database or use the example scripts under `docs/source/examples/` and `scripts/` |

The Crawler Admin UI at `http://localhost:3010/admin` is the operational
surface for schedules, manual runs, YAML editing, logs, and run history. It is
not the primary data browser, but it is the fastest way to see which crawlers
exist, which ones are enabled, and whether recent runs succeeded.

If you want to know where a specific dataset ends up:

- check the crawler page under [docs/source/crawlers/](docs/source/crawlers/README.md)
- inspect the crawler section in [CRAWLER_CONFIG.yml](CRAWLER_CONFIG.yml)
- query `public.metadata` in PostgreSQL after the first successful crawler run

## Configuration

The scheduler and helper scripts read crawler settings from `CRAWLER_CONFIG.yml`.
Important settings include:

- `enable`
- `schedule`
- `schema_name`
- `database_uri`
- crawler-specific options such as `forecast_hours` or `target_data_items`

Credentials and local operator overrides should not be committed. Keep them in
`crawler/.env` or another local environment mechanism.

Credentialed crawlers such as `entsoe_fms`, `energy_forecast_crawler`, and
`epex_spot` should be reviewed before the first scheduler run. On a fresh
deployment, set the required secrets and, for `entsoe_fms`, adjust
`default_start_date` if you do not want a full historical backfill.

On a clean installation, crawler-backed schemas and dashboards remain empty
until the first successful crawler run. For example, the `weather` schema and
its dashboard panels are created and populated only after the first
`weather_forecast` execution.

For local alert routing, `crawler/.env` can override the committed default email
recipients with `OEDS_EMAIL_TOADDRS`. That lets you test dashboard mail alerts
or scheduler error notifications without changing `CRAWLER_CONFIG.yml`.

If you run the scheduler or admin UI inside Docker, the containers override the
database host and port at runtime so that the existing local-style
`localhost:6432` URIs can still target `open-data:5432` on the internal Docker
network. That keeps the same `CRAWLER_CONFIG.yml` usable for both host and
container-based runs.

On deployment hosts, `OEDS_RUNTIME_DIR` can be used to move mutable runtime
files such as `CRAWLER_CONFIG.yml`, `crawler/.env`, `logs/`, and
`crawler_admin_state/` outside the Git checkout.

For public releases, treat deployment credentials, source API tokens, and local
operator notes as environment-specific material rather than repository content.

## Notable dashboards

Provisioned dashboards live under `data/provisioning/grafana/dashboards/` and
are grouped into crawler-specific subfolders plus `shared/`.
Examples include:

- `Weather Dashboard`
- `Energy Weather Dashboard`
- `ENTSOE Stress Cockpit`
- `ENTSOE Cross-Border & Price Spread Cockpit`
- `ENTSOE Negative Prices - Event 2026-04-26`
- `ENTSOE Negative Prices - Long-Term Analysis`
- `ENTSOE Transfer Capacity, Adequacy & Projects`

These dashboards depend on their related crawler schemas being populated.

## Documentation

For local and published documentation, start here:

- [Getting Started](docs/source/getting_started.md)
- [Deployment Guide](docs/source/deployment.md)
- [Crawler Documentation](docs/source/crawlers/README.md)
- [Crawler Configuration](docs/source/crawler_config.md)
- [Crawler Development](docs/source/crawler_development.md)
- [Crawler Admin UI](docs/source/crawler_admin.md)
- [Deployment Validation](docs/source/deployment_validation.md)
- [Examples](docs/source/examples/index.rst)
- [Ansible Playbooks](playbooks/README.md)

## Contributing

Contribution guidelines live in [CONTRIBUTING.md](CONTRIBUTING.md).

When adding a crawler or a new derived dataset:

1. add or update the crawler module under `crawler/`
2. register its scheduler entry in `CRAWLER_CONFIG.yml`
3. document it under `docs/source/crawlers/`
4. document authentication, source license, and downstream dependencies
5. add bootstrap SQL to `init.sql` if fresh installs need it
6. run the relevant checks before opening a change


## License

This repository is a KIT-maintained derivative of the Open Energy Data Server
project. It keeps the upstream lineage transparent through the Git history,
SPDX metadata, and the upstream link above while removing legacy assets that are
not part of the maintained KIT deployment path.

This project is licensed under `AGPL-3.0-or-later`. See
[`LICENSES/AGPL-3.0-or-later.txt`](LICENSES/AGPL-3.0-or-later.txt).
