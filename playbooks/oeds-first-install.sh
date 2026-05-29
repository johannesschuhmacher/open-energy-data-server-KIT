#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INVENTORY="${OEDS_INVENTORY:-inventory.yml}"
ANSIBLE_ARGS=("$@")

if [[ ! -f "$INVENTORY" ]]; then
  cp inventory.example.yml "$INVENTORY"
  echo "[INFO] Created $INVENTORY from inventory.example.yml."
  echo "[INFO] Edit $INVENTORY before rerunning this script if you install to a remote host."
fi

echo "[1/6] Refreshing local sudo credentials."
sudo -v

sudo_keepalive_pid=""
while true; do
  sudo -n true
  sleep 60
done &
sudo_keepalive_pid="$!"

cleanup() {
  if [[ -n "${sudo_keepalive_pid:-}" ]]; then
    kill "$sudo_keepalive_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[2/6] Installing required Ansible collections."
ansible-galaxy collection install -r requirements.yml

echo "[3/6] Checking Ansible connectivity."
ansible -i "$INVENTORY" "${ANSIBLE_ARGS[@]}" oeds -m ping

echo "[4/6] Checking target hostname."
ansible -i "$INVENTORY" "${ANSIBLE_ARGS[@]}" oeds -m command -a "hostname -f"

echo "[5/6] Preparing host packages and Docker."
ansible-playbook -i "$INVENTORY" "${ANSIBLE_ARGS[@]}" oeds-install-host-prep.yml

echo "[6/6] Installing OEDS with scheduler and Crawler Admin UI."
ansible-playbook -i "$INVENTORY" "${ANSIBLE_ARGS[@]}" oeds-install-crawlers.yml

echo "[DONE] OEDS first installation finished. The crawler install playbook already ran the smoke test."
