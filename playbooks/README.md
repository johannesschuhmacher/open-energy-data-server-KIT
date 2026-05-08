# OEDS Ansible Playbooks

These playbooks are the public installation and operations path for OEDS.
They cover generic host preparation, installation, updates, backups, database
migration, rollback, smoke tests, and uninstall workflows.

Secrets, inventories, host-specific overrides, and runtime data do not belong
in the repository. Keep them in local `group_vars`, untracked `.env` files, or
host-side runtime directories.

## Target layout

The playbooks install and operate OEDS on a Linux host with Docker Compose.
The Compose file stays in the repository checkout, while mutable runtime data
is stored outside the checkout.

Default target paths:

```text
/open_energy_data_server/repo          # OEDS repository checkout
/open_energy_data_server/docker_data   # persistent Docker volume data
/open_energy_data_server/runtime       # config, secrets, logs, admin state
/open_energy_data_server/backups       # backup and migration artifacts
```

Runtime extraction means that `CRAWLER_CONFIG.yml`, `crawler/.env`,
`crawler/data`, `logs`, and `crawler_admin_state` are stored outside the git
checkout. This allows repo updates or fresh checkouts without overwriting local
configuration, secrets, logs, or admin state.

Crawler containers read `crawler/.env` via Compose `env_file`. The file must
exist on the host, but it is not mounted into the container as a readable bind
mount.

Recommended split between public repo content and private operations data:

- Keep the versioned `CRAWLER_CONFIG.yml` generic and free of personal email
  recipients, production SMTP hosts, or credentials.
- Store real email recipients, SMTP credentials, and crawler secrets only in
  untracked files such as `crawler/.env`, host runtime `.env`, or
  `group_vars/oeds.yml`.
- Use `OEDS_EMAIL_TOADDRS`, `OEDS_EMAIL_MAILHOST`, `OEDS_EMAIL_FROMADDR`,
  `OEDS_EMAIL_USERNAME`, and `OEDS_EMAIL_PASSWORD` to override mail settings
  locally without editing the versioned YAML.

## Requirements

Control node:

- Linux or WSL is recommended. Ansible is not a good native Windows control
  node.
- SSH access as `root`. The current public playbooks use `remote_user: root`.
- `ansible` plus the collections from `requirements.yml`.

Install control-node dependencies:

```bash
uv tool install --with ansible-lint ansible
ansible-galaxy collection install -r requirements.yml
```

If you use WSL, clone the repository into the Linux filesystem when possible
instead of `/mnt/c/...`. In world-writable mounts Ansible ignores `ansible.cfg`.
If you still work from `/mnt/c/...`, always pass `-i inventory.yml` explicitly.
For playbook status mail support, load `ansible.cfg` explicitly:

```bash
ANSIBLE_CONFIG=playbooks/ansible.cfg ansible-playbook -i playbooks/inventory.yml playbooks/oeds-smoke-test.yml
```

Target host:

- A RHEL, Rocky, Alma, or CentOS compatible system with `dnf`.
- Python for Ansible modules.
- Network access to Docker registries and the selected git remote.
- Enough storage for PostgreSQL data and backups.

## Inventory and local variables

Create a local inventory:

```bash
cp inventory.example.yml inventory.yml
ansible -i inventory.yml oeds -m ping
```

Optional local variables:

```bash
mkdir -p group_vars
cp group_vars/oeds.example.yml group_vars/oeds.yml
```

`group_vars/oeds.yml` is intended for local host configuration and should stay
unversioned.

## Repository access and private rollouts

In the default `git` mode, the target host must be able to reach
`oeds_repo_url` on its own. For unpublished branches or commits, there are
three useful options:

- Give the host git access with a deploy key or token.
- Point the playbooks to an internal mirror the host can read.
- Use `oeds_repo_source_mode=local_archive` to build a local `git archive` on
  the control node and unpack it on the target host.

Example with a host-local mirror:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_url=/open_energy_data_server/backups/oeds.git \
  -e oeds_repo_version=<commit>
```

All public playbooks honor overrides from `group_vars/oeds.yml` or `-e` for:

- `oeds_repo_url`
- `oeds_repo_version`
- `oeds_root`
- `oeds_runtime_dir`
- `oeds_data_dir`

Example local-archive rollout:

```bash
ansible-playbook -i inventory.yml oeds-update.yml \
  -e oeds_repo_source_mode=local_archive \
  -e oeds_repo_local_src=/path/to/oeds \
  -e oeds_repo_version=main \
  -e oeds_enable_crawlers=true
```

In `git` mode, the playbooks verify repo access before any downtime step with
`GIT_TERMINAL_PROMPT=0`. Missing credentials fail fast instead of hanging in a
blocked `git fetch`.

## Playbook status emails

The public playbooks ship an Ansible callback plugin named `oeds_mail`. When
`ansible.cfg` is loaded and SMTP sender, recipient, and host are configured,
the callback sends one status email at the end of each playbook run.

- Successful runs are reported as `SUCCESS`.
- Runtime failures and unreachable hosts are reported as `FAILED`.
- Syntax errors that happen before callback plugins are loaded cannot trigger
  emails.

The callback can use the same local mail overrides as the crawler runtime:

```bash
export OEDS_EMAIL_MAILHOST=smtp.example.com:25
export OEDS_EMAIL_FROMADDR=oeds@example.com
export OEDS_EMAIL_TOADDRS=person1@example.com,person2@example.com
```

Dedicated Ansible mail variables take precedence:

```bash
export OEDS_ANSIBLE_EMAIL_MAILHOST=smtp.example.com:587
export OEDS_ANSIBLE_EMAIL_FROMADDR=oeds-ansible@example.com
export OEDS_ANSIBLE_EMAIL_TOADDRS=ops@example.com
export OEDS_ANSIBLE_EMAIL_STARTTLS=true
export OEDS_ANSIBLE_EMAIL_USERNAME=smtp-user
export OEDS_ANSIBLE_EMAIL_PASSWORD='...'
```

If `crawler/.env` exists on the control node, it is used as a fallback source
for `OEDS_EMAIL_*`. Keep secrets in local environment variables or untracked
`.env` files, never in the repository.

Dry-run example:

```bash
ANSIBLE_CONFIG=playbooks/ansible.cfg \
OEDS_ANSIBLE_EMAIL_DRY_RUN=true \
OEDS_ANSIBLE_EMAIL_DRY_RUN_FILE=/tmp/oeds-ansible-status.eml \
OEDS_ANSIBLE_EMAIL_MAILHOST=localhost \
OEDS_ANSIBLE_EMAIL_FROMADDR=oeds@example.com \
OEDS_ANSIBLE_EMAIL_TOADDRS=ops@example.com \
ansible-playbook -i playbooks/inventory.yml playbooks/oeds-smoke-test.yml
```

## Installation options

The public entry points are wrapper playbooks that call the lower-level tasks
in the correct order.

### Option 1: Local developer start

Without Ansible, directly from the repository:

```bash
docker compose up -d
```

With crawler containers:

```bash
docker compose --profile crawlers up -d --build
```

This is the fastest path for local testing, but not a full server setup.

### Option 2: Prepare a new host

Install OS repositories, SELinux policy, and packages:

```bash
ansible-playbook -i inventory.yml oeds-install-host-prep.yml
```

Use this on a fresh Linux host. If Docker is already installed and working, you
can skip this step.

### Option 3: Install OEDS core services

Install packages, Docker volumes, runtime directories, the repo checkout, and
start PostgreSQL, PostgREST, Grafana, and PgAdmin:

```bash
ansible-playbook -i inventory.yml oeds-install-core.yml \
  -e oeds_repo_version=<branch-tag-or-commit>
```

This is the recommended minimal path for a server without the scheduler and
without the crawler admin UI.

Portainer is intentionally optional. If you want it, start it explicitly as an
ops profile after the core install:

```bash
cd /open_energy_data_server/repo
docker compose --profile ops up -d portainer portainer_agent
```

### Option 4: Install OEDS with crawler services

Install the core stack plus the scheduler and crawler admin UI containers:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_version=<branch-tag-or-commit>
```

This is the recommended default path for a long-running OEDS instance. The
selected `oeds_repo_version` must include the `crawlers` compose profile.

Example first run on a clean test VM:

```bash
ansible -i inventory.yml oeds -m ping
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true \
  -e oeds_uninstall_remove_runtime=true \
  -e oeds_uninstall_destroy_data=true \
  -e oeds_uninstall_confirm=DELETE_OEDS_DATA
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_version=<commit>
ansible-playbook -i inventory.yml oeds-smoke-test.yml \
  -e oeds_expect_crawler_admin=true
```

A clean install is not a fully populated OEDS instance. Crawler-dependent
schemas and dashboards only become useful after the first successful crawler
run. The validation flow therefore includes at least one manual
`weather_forecast` run through the crawler admin UI.

For production, `oeds_repo_version` should point to a tested branch, tag, or
commit, not a floating `latest`.

## Update workflow

Use this playbook for normal application, Compose, and container-image updates:

```bash
ansible-playbook -i inventory.yml oeds-update.yml \
  -e oeds_repo_version=<branch-tag-or-commit> \
  -e oeds_enable_crawlers=true
```

The update playbook:

- creates a logical database backup if the DB is running,
- stops legacy Compose projects,
- checks out the requested repo version,
- writes `.env` with `OEDS_RUNTIME_DIR`,
- refreshes Grafana, PgAdmin, and SQL provisioning from the repo,
- runs `docker compose pull` and `docker compose up -d`,
- blocks accidental PostgreSQL major upgrades.

Optional OS package updates:

```bash
ansible-playbook -i inventory.yml oeds-update.yml \
  -e oeds_update_docker_packages=true \
  -e oeds_update_nginx=true \
  -e oeds_update_certbot=true
```

Set these flags deliberately rather than leaving them enabled by default.

## PostgreSQL and TimescaleDB migration

A PostgreSQL major upgrade must not happen just by swapping the image. Use the
dedicated migration playbook.

1. Create a backup:

```bash
ansible-playbook -i inventory.yml oeds-db-backup.yml
```

2. Restore into staging first:

```bash
ansible-playbook -i inventory.yml oeds-db-migrate.yml \
  -e oeds_apply_cutover=false
```

3. Validate the staging result, review logs, and run smoke tests.

4. Apply cutover only after validation:

```bash
ansible-playbook -i inventory.yml oeds-db-migrate.yml \
  -e oeds_apply_cutover=true \
  -e oeds_enable_crawlers_after_cutover=true
```

5. Run the smoke test:

```bash
ansible-playbook -i inventory.yml oeds-smoke-test.yml \
  -e oeds_expect_crawler_admin=true
```

## Rollback

Rollback expects an older PostgreSQL data directory, for example from a
migration backup:

```bash
ansible-playbook -i inventory.yml oeds-db-rollback.yml \
  -e oeds_rollback_source_dir=/open_energy_data_server/backups/<run-id>/postgres-home-pre-cutover \
  -e oeds_enable_crawlers_after_rollback=true
```

## Uninstall and test reset

Conservative uninstall without deleting data:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml
```

This removes containers and Docker networks but keeps the repo checkout,
runtime files, backups, and Docker volumes. Docker itself, nginx, firewall
rules, and TLS assets are not removed.

Fresh test run with a new repo checkout:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true
```

Full test-VM reset including database volumes, runtime config, and repo:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true \
  -e oeds_uninstall_remove_runtime=true \
  -e oeds_uninstall_destroy_data=true \
  -e oeds_uninstall_confirm=DELETE_OEDS_DATA
```

To remove backups and cached Docker images as well:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true \
  -e oeds_uninstall_remove_runtime=true \
  -e oeds_uninstall_destroy_data=true \
  -e oeds_uninstall_remove_backups=true \
  -e oeds_uninstall_remove_images=true \
  -e oeds_uninstall_confirm=DELETE_OEDS_DATA
```

After that, rebuild the VM with one of the installation levels, for example:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_version=<branch-tag-or-commit>
```

## Playbook reference

- `oeds-install-host-prep.yml`: prepare a new host with packages and OS-level
  dependencies.
- `oeds-install-core.yml`: install the OEDS core stack without crawler
  services.
- `oeds-install-crawlers.yml`: install the core stack plus scheduler and
  crawler admin UI.
- `oeds-packages.yml`: install nginx and Docker/Compose packages.
- `oeds-docker-config.yml`: initialize Docker volumes, runtime directories,
  the repo checkout, and the Compose stack.
- `oeds-update.yml`: roll out a new repo, Compose, or image version.
- `oeds-db-backup.yml`: create database, extension, Compose, and runtime
  backups.
- `oeds-db-migrate.yml`: migrate PostgreSQL/TimescaleDB via dump/restore into
  a new target container and optionally apply cutover.
- `oeds-db-rollback.yml`: restore the live PostgreSQL data path from an older
  data snapshot.
- `oeds-uninstall.yml`: stop and remove OEDS containers and networks; delete
  data, runtime, repo, backups, or images only when explicitly requested.
- `oeds-smoke-test.yml`: verify PostgreSQL, PostgREST, Grafana, PgAdmin, and
  optionally the crawler admin UI. HTTP endpoints are checked with retries to
  avoid false alarms on fresh startups.

Reverse proxy, TLS, and firewall customization are intentionally not part of
the public default path and should be maintained outside this repository.

## Repository boundary

The public playbooks belong in the repository as long as this boundary is kept:

- Generic install, update, backup, migration, rollback, and smoke-test logic
  may stay in the repo.
- `inventory.yml`, `group_vars/oeds.yml`, secrets, and runtime data remain
  private.
- Internal institution-specific deployment playbooks belong in private ops
  overlays, not in the public branch.
- Updates should use tested tags, branches, or commits, not uncontrolled
  floating versions.

## Validated deployment state

The externally validated install and test run is documented in
[../docs/source/deployment_validation.md](../docs/source/deployment_validation.md).
That document covers the tested sequence of uninstall, clean install, smoke
test, admin configuration changes, and the first manual crawler run.
