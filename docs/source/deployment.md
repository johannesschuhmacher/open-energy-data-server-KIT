# Deployment Guide

This guide describes a public, reusable deployment path for OEDS-KIT without
the old internal VM notes.

## What gets deployed

The repository ships a `compose.yml` for the core services:

- PostgreSQL with TimescaleDB
- PgAdmin
- PostgREST
- Grafana

Optional crawler services are also available in the same Compose file through
the `crawlers` profile:

- `scheduler`
- `crawler-admin`

You can still run crawlers manually or through an external process manager, but
the repository now supports containerized scheduler and admin deployments
without splitting them into a single multi-process container.

## Prerequisites

Before deploying on a long-lived host, make sure you have:

- Docker with the Compose plugin
- `uv`, if you plan to run crawlers directly on the host
- a writable host path for database and provisioning data
- a writable host path for crawler runtime data such as `logs/` and
  `crawler_admin_state/`
- a `crawler/.env` file for crawler secrets when using the containerized
  scheduler or admin UI
- credentials for any authenticated crawler sources you plan to enable

## Source licensing and access

Before enabling a crawler on a public or shared deployment, verify:

- whether the upstream source is open, credentialed, or proprietary
- whether local storage is permitted
- whether downstream republication is permitted
- whether the source imposes rate limits or account restrictions

OEDS can technically integrate all of these source types, but the legal and
operational responsibilities stay with the deployment operator.

## 1. Prepare the repository and storage paths

Clone the repository to the target host and review `compose.yml`.

The current Compose file uses named Docker volumes for persistent service data
and bind mounts repository files for SQL initialization and Grafana/PgAdmin
provisioning. This keeps the local path simple while still allowing the Ansible
playbooks to pre-create named volumes with host-backed storage on long-lived
servers.

If you are upgrading an existing deployment that already contains PostgreSQL or
TimescaleDB data from an older major version, plan a database migration first.
Switching the container image to PostgreSQL 18 is not an in-place storage
upgrade. Use `pg_upgrade` or a dump/restore workflow before pointing the new
container at the existing data directory.

Persistent named volumes from the current file:

- `postgres-home`
- `pgadmin-varlib`
- `grafana-varlib`
- optional `portainer-data`

Provisioning files are mounted directly from the repository:

- `docker/initdb/10-init.sql`
- `scripts/lib/postgres_functions.sql`
- `data/provisioning/grafana/...`
- `data/provisioning/pgadmin/servers.json`

## 2. Review service credentials before exposure

The repository defaults in `compose.yml` are intentionally insecure. They exist
so the public repository can still bootstrap isolated local, internal, or
disposable test systems without a separate secret-management layer.

Do not expose a host that still uses these defaults on a shared or public
network.

Before the first startup of any shared or longer-lived host, set at least:

- `OEDS_DB_PASSWORD`
- `OEDS_READONLY_PASSWORD`
- `OEDS_GRAFANA_ADMIN_PASSWORD`
- `OEDS_PGADMIN_DEFAULT_PASSWORD`

If you keep the public Compose defaults, treat the deployment as insecure and
internal-only:

- PostgreSQL stays on `opendata/opendata`
- PostgREST and Grafana use `readonly/readonly` for database access
- Grafana admin stays on `opendata/opendata`
- PgAdmin stays on `admin@admin.admin` / `admin`

On any non-disposable server, also:

- review whether anonymous Grafana access should stay enabled
- restrict network exposure for PgAdmin and PostgREST if they are not meant to
  be public

## 3. Prepare crawler credentials

Create `crawler/.env` from `crawler/.env.example` and add only the secrets
needed by the crawlers you plan to run.

Common examples in this repository:

- `ENTSOE_USERNAME`
- `ENTSOE_PASSWORD`
- `ENTSOE_API_KEY`
- `ENERGY_FORECAST_TOKEN`
- `OEDS_EMAIL_TOADDRS`
- optional `OEDS_EMAIL_MAILHOST`, `OEDS_EMAIL_FROMADDR`,
  `OEDS_EMAIL_USERNAME`, and `OEDS_EMAIL_PASSWORD`

`ENTSOE_API_KEY` is not the same secret as the ENTSO-E FMS login. The FMS
crawler uses `ENTSOE_USERNAME` and `ENTSOE_PASSWORD`; the Web API crawler uses a
generated Transparency Platform security token. `ENTSOE_API` is accepted as a
local alias for that token. The day-ahead price forecast is scheduled from
`entsoe_api`, so productive forecast deployments need this API token.

Do not commit this file.

## 4. Review `CRAWLER_CONFIG.yml`

Before enabling scheduled runs, check these values for each active crawler:

- `enable`
- `schema_name`
- `database_uri`
- `schedule`
- crawler-specific parameters such as `forecast_hours`, `dataset_id`, or
  `target_data_items`

For a fresh deployment, keep credentialed crawlers disabled until their secrets
and initial backfill windows are reviewed. In particular, `entsoe_fms` supports
`default_start_date` so you can narrow the first historical import before the
first scheduler run.

If you deploy separate environments, keep database URIs and enabled crawlers
explicit instead of relying on local defaults.

## 5. Start the core services

From the repository root:

```bash
docker compose up -d
```

Then verify the services:

- PostgreSQL on `localhost:6432`
- PgAdmin on `http://localhost:8080/`
- PostgREST on `http://localhost:3001/`
- Grafana on `http://localhost:3006/`

If one of those host ports is already used, override it before starting
Compose, for example:

```bash
OEDS_POSTGRES_PORT=16432 OEDS_GRAFANA_PORT=13006 docker compose up -d
```

If you also want the scheduler and admin UI in Docker, start the crawler
profile as well:

```bash
docker compose --profile crawlers up -d scheduler crawler-admin
```

If you also want the optional Portainer UI, start the `ops` profile
separately:

```bash
docker compose --profile ops up -d portainer portainer_agent
```

The crawler profile uses one shared Python image with two separate services and
persists:

- `CRAWLER_CONFIG.yml` as a bind mount so admin edits survive rebuilds
- `crawler/.env` as a Compose `env_file` for crawler credentials
- `crawler/data/` for crawler-generated local files
- `logs/` for scheduler and crawler log files
- `crawler_admin_state/` for admin run history and per-run metadata

The crawler image installs the `price-forecast` dependency group, including the
pinned upstream `DA_Price_Forecasting_Pipeline_DE_LU` package. Compose also
sets default forecast runtime options for the scheduler:

- `OEDS_PRICE_FORECAST_BACKEND=auto`
- `OEDS_PRICE_FORECAST_MARKET_AREA=DE_LU`
- `OEDS_PRICE_FORECAST_TRAIN_DAYS=56`
- `OEDS_PRICE_FORECAST_BACKTEST_DAYS=2`
- `OEDS_PRICE_FORECAST_RETENTION_DAYS=180`

Override these environment variables when a deployment needs a different
market area, backtest cadence, or retention window.

On long-lived hosts, set `OEDS_RUNTIME_DIR` so these mutable files live outside
the Git checkout, for example under `/open_energy_data_server/runtime`.

## Ansible deployment levels

The repository also contains Ansible playbooks under `playbooks/` for server
installations and updates. The recommended entry points are:

- `oeds-install-core.yml` for database, PostgREST, Grafana, PgAdmin, and
  the default core services.
- `oeds-install-crawlers.yml` for the core stack plus scheduler and crawler
  admin UI through the Compose `crawlers` profile.
- `oeds-update-crawlers.yml` for updates on installations that run the crawler
  profile and stay on the public defaults.
- optional operator-specific edge playbooks for reverse proxy, TLS, or
  firewalling, if you decide to maintain them outside the public repository.

Operator-specific files such as `inventory.yml`, `group_vars/oeds.yml`, and
secret-bearing crawler environment files should stay local and are ignored by
the playbook folder's `.gitignore`.

For the simplest public install, copy `playbooks/inventory.example.yml` to
`playbooks/inventory.yml` and run `oeds-install-crawlers.yml` without extra
overrides. The playbooks already default to the public GitHub repository on
`main`, and the example inventory is prefilled for a same-host install with
`sudo`. Create `group_vars/oeds.yml` only when you need to override the git
remote, ref, or target directories.

The target host must also be able to clone `oeds_repo_url` itself. For
unpublished or internal test branches, either give the host Git access to the
real remote or override `oeds_repo_url` with a reachable mirror or local bare
repository on the target system.

If you drive Ansible from WSL, prefer cloning the repository inside the Linux
filesystem instead of under `/mnt/c/...`; otherwise Ansible may ignore
`ansible.cfg` because the working directory is world-writable.

The playbooks include the `oeds_mail` Ansible callback for end-of-run status
notifications. It sends a success or failure email when `ansible.cfg` is loaded
and SMTP settings are provided via local environment variables, for example
`OEDS_ANSIBLE_EMAIL_MAILHOST`, `OEDS_ANSIBLE_EMAIL_FROMADDR`, and
`OEDS_ANSIBLE_EMAIL_TOADDRS`. If those playbook-specific variables are absent,
the callback falls back to the existing crawler mail overrides
`OEDS_EMAIL_MAILHOST`, `OEDS_EMAIL_FROMADDR`, and `OEDS_EMAIL_TOADDRS`.

## 6. Run initial crawler loads manually

Before enabling unattended scheduling, run the important crawlers once by hand:

```bash
uv run python -m crawler.weather_forecast
uv run python -m crawler.entsoe_fms
uv run python -m crawler.entsoe_api
uv run python -m crawler.energy_forecast_crawler
```

This is the fastest way to catch missing credentials, schema issues, or source
API problems before they are hidden inside a scheduler service.

## 7. Run the scheduler

The repository scheduler entry point is:

```bash
uv run python crawler_scheduler.py
```

For a persistent deployment, run this through your process supervisor of
choice, for example:

- `systemd`
- a containerized worker service
- another scheduler framework you already operate

The admin UI entry point is:

```bash
uv run python crawler_admin_server.py
```

If you use the provided Docker services, Compose sets `OEDS_DB_HOST=open-data`
and `OEDS_DB_PORT=5432` so that the same `CRAWLER_CONFIG.yml` can stay usable
even when it still contains host-style `localhost:6432` database URIs.

Recommended split between public and private configuration:

- keep the committed `CRAWLER_CONFIG.yml` generic and free of personal email
  addresses, institution-specific SMTP hosts, or live credentials
- keep real crawler secrets and mail routing only in unversioned files such as
  local `crawler/.env`, host runtime `crawler/.env`, or ignored Ansible
  `group_vars/oeds.yml`
- let the target host runtime own mutable operational files under
  `/open_energy_data_server/runtime/`, while the repository remains a neutral
  installable baseline

## 8. Verify the deployment

After the first successful crawler runs, verify:

- target schemas and tables exist in PostgreSQL
- `public.metadata` contains the expected dataset entries
- Grafana dashboards load without empty-source errors
- PostgREST can see the expected schemas or views

## 9. Production notes

For a public or shared deployment, also plan for:

- database backups and restore tests
- TLS and reverse-proxy setup for web-facing services
- least-privilege database roles for API access
- secret rotation
- log retention and crawler failure alerting

The public docs in this repository are meant to describe the reusable platform.
Host-specific inventories, internal tokens, and one-off deployment overrides
should stay outside the published documentation.
