<!-- SPDX-FileCopyrightText: OEDS Contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Installation

This guide installs OEDS on a clean Linux server.

## Target system

Use a CentOS/RHEL-compatible Linux server with `dnf`, for example:

- CentOS Stream
- Rocky Linux
- AlmaLinux
- Red Hat Enterprise Linux

You need a user with `sudo` rights. Native Windows is not a supported server
target. Use Windows only for local Docker Desktop testing, or use WSL/Linux as
an Ansible control node.

Check sudo before you start:

```bash
sudo -v
```

If this asks for a password and succeeds, the user has the required sudo
rights. The first-install script below refreshes this sudo cache once and keeps
it alive while the installation runs, so you normally enter the password only
once during the first install.

For later one-off commands, either run `sudo -v` immediately before Ansible or
add `-K` to the Ansible command. `-K` means "ask for the sudo password".

## 1. Install basic tools

On the target server:

```bash
sudo dnf install -y git python3 python3-pip
python3 -m pip install --user ansible
export PATH="$HOME/.local/bin:$PATH"
```

Check that Ansible is available:

```bash
ansible --version
ansible-playbook --version
```

## 2. Clone OEDS

```bash
sudo mkdir -p /open_energy_data_server
sudo chown -R "$USER:$USER" /open_energy_data_server
git clone https://github.com/johannesschuhmacher/open-energy-data-server-KIT.git /open_energy_data_server/repo
cd /open_energy_data_server/repo/playbooks
```

## 3. Run the first-install script

The first-install script does the normal first-run sequence:

- install required Ansible collections
- create `inventory.yml` from `inventory.example.yml` if it does not exist yet
- refresh and keep the local sudo cache alive
- check Ansible connectivity
- check the target hostname
- prepare the host
- install OEDS with scheduler and Crawler Admin UI
- run the smoke test through the crawler install playbook

For a same-host install, run:

```bash
./oeds-first-install.sh
```

If you need extra Ansible options, pass them after the script name:

```bash
./oeds-first-install.sh -e oeds_repo_version=<branch-tag-or-commit>
```

The script is intended for the simple same-host install path. For a remote
host, create and edit `inventory.yml` first, then run the same script:

```bash
cp inventory.example.yml inventory.yml
vi inventory.yml
./oeds-first-install.sh
```

The sudo cache approach helps the same-host install because Ansible uses local
sudo on the same machine. For remote installs where the target host asks for a
sudo password, use `-K` or configure the remote sudo policy explicitly.

The individual steps have different jobs:

- Step 4 checks that Ansible is talking to the right machine and can use sudo.
  It does not install OEDS.
- Step 5 prepares a clean CentOS/RHEL-compatible host. It configures package
  repositories, SELinux handling, and Docker packages. Run it once on a fresh
  server.
- Step 6 deploys OEDS itself. It creates runtime configuration, updates the
  repository checkout, starts Docker Compose, and runs the smoke test.

If you do not use the script, run the manual steps in order. Seeing Docker
package checks again in step 6 is expected; that playbook repeats the package
step so updates and direct installs stay safe.

## 4. Manual inventory check

You can run the inventory checks manually, for example after editing a remote
inventory:

```bash
ansible -i inventory.yml oeds -m ping
ansible -i inventory.yml oeds -m command -a "hostname -f"
```

The hostname check should show the server you intend to install.

The example inventory uses `sudo` through `ansible_become: true`. If a manual
command fails with `sudo: a password is required`, either refresh sudo first:

```bash
sudo -v
ansible -i inventory.yml oeds -m ping
```

or rerun it with `-K` and enter the sudo password:

```bash
ansible -i inventory.yml oeds -m ping -K
ansible -i inventory.yml oeds -m command -a "hostname -f" -K
```

Use the same `-K` flag for later manual `ansible-playbook` commands when sudo
requires a password and you did not refresh the sudo cache:

```bash
ansible-playbook -i inventory.yml oeds-install-host-prep.yml -K
ansible-playbook -i inventory.yml oeds-install-crawlers.yml -K
ansible-playbook -i inventory.yml oeds-smoke-test.yml -K \
  -e oeds_expect_crawler_admin=true
```

On a disposable test VM, passwordless sudo is also possible. Configure it only
if this matches your local security policy:

```bash
echo 'oeds ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/oeds
sudo chmod 0440 /etc/sudoers.d/oeds
sudo visudo -cf /etc/sudoers.d/oeds
```

If Ansible prints `Unable to parse inventory.yml`, recreate the file from
`inventory.example.yml` and check that it starts with:

```yaml
---
all:
  children:
    oeds:
```

For a remote install, edit `inventory.yml` and replace the `localhost` host
with `ansible_host` and, if needed, `ansible_user`.

## 5. Manual host preparation

On a clean CentOS/RHEL-compatible server, install Docker and required host
packages through the host-prep playbook:

```bash
ansible-playbook -i inventory.yml oeds-install-host-prep.yml
```

If Docker with the Compose plugin is already installed and working, this step
can be skipped.

## 6. Manual OEDS install

Install the core stack plus scheduler and crawler admin UI:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml
```

The install uses the public GitHub `main` branch by default.

## 7. Verify the installation

The install wrapper already runs the smoke test. You can run it again
explicitly. Add `-K` when sudo asks for a password:

```bash
ansible-playbook -i inventory.yml oeds-smoke-test.yml \
  -e oeds_expect_crawler_admin=true
```

```bash
ansible-playbook -i inventory.yml oeds-smoke-test.yml -K \
  -e oeds_expect_crawler_admin=true
```

Then open:

- Grafana: `http://<server>:3006/`
- PgAdmin: `http://<server>:8080/`
- PostgREST: `http://<server>:3001/`
- Crawler Admin: `http://<server>:3010/admin`

For a same-host shell test, use `127.0.0.1` instead of `<server>`.

## Optional: deploy a local checkout

Use this only when the target server cannot clone the desired branch, tag, or
commit from GitHub.

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_source_mode=local_archive \
  -e oeds_repo_local_src=/home/oeds/open-energy-data-server \
  -e oeds_repo_version=HEAD
```

`local_archive` packages the selected Git ref on the Ansible control node and
copies it to the target. Only committed, tracked files are included. Commit
your intended changes before using this mode.

## Optional: reset a test machine

This deletes containers, Docker volumes, runtime files, backups, and cached
images. Use it only on a disposable test host:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true \
  -e oeds_uninstall_remove_runtime=true \
  -e oeds_uninstall_destroy_data=true \
  -e oeds_uninstall_remove_backups=true \
  -e oeds_uninstall_remove_images=true \
  -e oeds_uninstall_confirm=DELETE_OEDS_DATA
```

Add `-K` after the playbook name if sudo requires a password.

Do not run this from inside `/open_energy_data_server/repo/playbooks` if
`oeds_uninstall_remove_repo=true`, because it deletes the checkout you are
standing in. Copy `playbooks/` to `/tmp` first or reinstall from a fresh clone.
