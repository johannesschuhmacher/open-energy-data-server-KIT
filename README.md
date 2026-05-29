<!-- SPDX-FileCopyrightText: Florian Maurer, Christian Rieke, Andre Meyer, Haoshen Zhang, Johannes Schuhmacher -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Open Energy Data Server

Open Energy Data Server (OEDS-KIT) is a crawler-driven data platform for
energy-system analysis. It collects energy data, stores it in
PostgreSQL/TimescaleDB, exposes database objects through PostgREST, and ships
Grafana dashboards for exploration.

Full documentation is available on
[Read the Docs](https://open-energy-data-server-kit.readthedocs.io/en/latest/).

![OEDS architecture overview](docs/source/media/oeds-architecture.png)

## What Is Included

- PostgreSQL/TimescaleDB with PostGIS
- PostgREST for HTTP access to database objects
- Grafana with provisioned dashboards
- crawler modules for energy, market, weather, and registry data
- a scheduler and Crawler Admin UI for operations
- Ansible playbooks for reproducible server installs

## Choose Your Path

- **Install OEDS on a clean server:** start with [INSTALLATION.md](INSTALLATION.md).
- **Try the stack locally:** use Docker Compose from this README.
- **Operate or customize a deployment:** use the
  [Deployment Guide](docs/source/deployment.md) and
  [Crawler Admin UI docs](docs/source/crawler_admin.md).
- **Find crawler-specific details:** use the
  [Crawler Documentation](docs/source/crawlers/README.md).

For real deployments, use a Linux server. The Ansible install path is intended
for CentOS/RHEL-compatible systems with `dnf`, such as CentOS Stream, Rocky
Linux, AlmaLinux, or RHEL. Native Windows is not a supported server target.

## Local Quick Start

You need Docker with the Compose plugin.

```bash
docker compose up -d
```

This starts:

- PostgreSQL/TimescaleDB: `localhost:6432`
- PgAdmin: `http://localhost:8080/`
- PostgREST: `http://localhost:3001/`
- Grafana: `http://localhost:3006/`

To also start the scheduler and Crawler Admin UI:

```bash
docker compose --profile crawlers up -d --build scheduler crawler-admin
```

Then open the Crawler Admin UI at `http://localhost:3010/admin`.

The public Compose defaults use insecure fallback credentials. They are useful
for local and disposable test systems only. Do not expose a deployment that
still uses the default passwords.

## Server Installation

For a clean server install, use [INSTALLATION.md](INSTALLATION.md). It contains
the exact commands for:

- installing Ansible and required collections
- cloning the repository to `/open_energy_data_server/repo`
- creating and checking `playbooks/inventory.yml`
- running the first-install script with a refreshed sudo cache
- preparing Docker on a CentOS/RHEL-compatible host
- installing OEDS with scheduler and Crawler Admin UI
- running the smoke test
- resetting a disposable test machine

## Common Entry Points

- `compose.yml`: local and server Compose stack
- `CRAWLER_CONFIG.yml`: default crawler configuration
- `crawler_scheduler.py`: scheduler entry point
- `crawler_admin_server.py`: Crawler Admin UI entry point
- `playbooks/`: installation, update, backup, smoke-test, and uninstall playbooks
- `docs/source/`: Read the Docs source

## Documentation

- [Installation](INSTALLATION.md)
- [Getting Started](docs/source/getting_started.md)
- [Deployment Guide](docs/source/deployment.md)
- [Crawler Admin UI](docs/source/crawler_admin.md)
- [Crawler Documentation](docs/source/crawlers/README.md)
- [Crawler Configuration](docs/source/crawler_config.md)
- [Troubleshooting](docs/source/troubleshooting.md)
- [Contributing](CONTRIBUTING.md)

## Development

Python development uses `uv` and the pinned project environment:

```bash
uv sync --locked
uv run --with pytest python -m pytest tests
uv run --only-group docs sphinx-build -b dummy docs/source docs/_build/dummy
```

For host-side crawler execution, some dependencies such as `pygrib` require
native libraries. On Windows, Docker or WSL is usually the simpler path.

## License

This repository is a KIT-maintained derivative of the original Open Energy Data
Server project and keeps the upstream lineage visible through Git history and
SPDX metadata.

This project is licensed under `AGPL-3.0-or-later`. See
[LICENSES/AGPL-3.0-or-later.txt](LICENSES/AGPL-3.0-or-later.txt).
