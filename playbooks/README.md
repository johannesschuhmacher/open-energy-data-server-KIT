# OEDS Ansible Playbooks

Diese Playbooks sind der oeffentliche Betriebs- und Installationspfad fuer
OEDS. Sie decken generische OEDS-Installation, Update, Backup, Migration und
Rollback ab. Inventories, lokale Variablen, Secrets und Host-spezifische
Overrides gehoeren nicht ins Repository.

## Zielbild

Die Playbooks installieren und betreiben OEDS auf einem Linux-Host mit Docker
Compose. Die Compose-Datei kommt aus dem OEDS-Repository, mutable Runtime-Daten
liegen ausserhalb des Git-Checkouts.

Standardpfade auf dem Zielhost:

```text
/open_energy_data_server/repo          # Git checkout des OEDS-Repos
/open_energy_data_server/docker_data   # persistente Docker-Volume-Daten
/open_energy_data_server/runtime       # Config, Secrets, Logs, Admin-State
/open_energy_data_server/backups       # Backup- und Migrationsartefakte
```

Das "Rausziehen" der Runtime-Dateien bedeutet: `CRAWLER_CONFIG.yml`,
`crawler/.env`, `crawler/data`, `logs` und `crawler_admin_state` liegen nicht
mehr nur im Git-Checkout. Dadurch kann das Repo aktualisiert oder neu
ausgecheckt werden, ohne lokale Konfiguration, Secrets, Logs oder Admin-State zu
ueberschreiben. Die Crawler-Container lesen `crawler/.env` dabei als Compose
`env_file`; die Datei muss also auf dem Host vorhanden sein, wird aber nicht als
lesbare Datei in den Container gemountet.

Empfehlung fuer oeffentliches Repo vs. private Betriebsdaten:

- das versionierte `CRAWLER_CONFIG.yml` bleibt generisch und enthaelt keine
  persoenlichen Empfaengeradressen, produktiven SMTP-Hosts oder Zugangsdaten
- echte Mail-Empfaenger, SMTP-Zugangsdaten und Crawler-Secrets liegen nur in
  unversionierten Dateien wie `crawler/.env`, Host-Runtime-`.env` oder
  `group_vars/oeds.yml`
- Admin-UI und Scheduler koennen Mailziele lokal ueber
  `OEDS_EMAIL_TOADDRS`, `OEDS_EMAIL_MAILHOST`, `OEDS_EMAIL_FROMADDR`,
  `OEDS_EMAIL_USERNAME` und `OEDS_EMAIL_PASSWORD` ueberschreiben, ohne die
  versionierte YAML anzufassen

## Voraussetzungen

Auf dem Control Node:

- Linux oder WSL wird empfohlen; Ansible ist kein sinnvoller nativer
  Windows-Control-Node.
- SSH-Zugriff als `root`. Die aktuellen Playbooks setzen `remote_user: root`
  direkt in den Plays.
- `ansible-core` oder `ansible`.
- Collections aus `requirements.yml`.

Installation auf dem Control Node:

```bash
uv tool install --with ansible-lint ansible
ansible-galaxy collection install -r requirements.yml
```

Wenn du WSL nutzt, clone das Repository moeglichst in das Linux-Dateisystem
statt unter `/mnt/c/...`. In world-writable Mounts ignoriert Ansible `ansible.cfg`.
Falls du trotzdem aus `/mnt/c/...` arbeitest, uebergib `-i inventory.yml`
explizit bei jedem Aufruf.

Auf dem Zielhost:

- RHEL/CentOS/Rocky/Alma-kompatibles System mit `dnf`.
- Python fuer Ansible-Module.
- Netzwerkzugang zu Docker-Repos, GitHub oder einem anderen erreichbaren
  Git-Remote und Container-Registries.
- Genug Speicherplatz fuer PostgreSQL-Daten und Backups.

## Inventory

`inventory.example.yml` kopieren und als `inventory.yml` anpassen:

```bash
cp inventory.example.yml inventory.yml
```

Beispielaufruf:

```bash
ansible -i inventory.yml oeds -m ping
```

Optionale zentrale Variablen:

```bash
mkdir -p group_vars
cp group_vars/oeds.example.yml group_vars/oeds.yml
```

`group_vars/oeds.yml` ist fuer lokale Zielhost-Konfiguration gedacht und sollte
nicht versioniert werden.

## Repo-Zugriff und privater Rollout

Der Zielhost muss `oeds_repo_url` selbst per `git clone` erreichen koennen.
Fuer eine noch nicht veroeffentlichte Branch-/Commit-Version gibt es drei
sinnvolle Wege:

- Git-Zugriff der VM per Deploy-Key oder Token auf das echte Remote.
- internen Mirror, den die VM lesen darf.
- lokalen bare Mirror auf dem Zielhost und Override per Extra-Var:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_url=/open_energy_data_server/backups/oeds.git \
  -e oeds_repo_version=<commit>
```

Wichtig: `oeds_repo_url`, `oeds_repo_version`, `oeds_root`, `oeds_runtime_dir`
und `oeds_data_dir` lassen sich jetzt ueber `group_vars/oeds.yml` oder `-e`
ueberschreiben. Die Playbooks verwenden dafuer keine fest verdrahteten
Pfadwerte mehr.

Fuer private Repositories oder ungepushte Teststaende koennen Install- und
Update-Playbooks den OEDS-Stand jetzt auch direkt vom Control Node auf den
Zielhost ausrollen. Dafuer wird lokal ein `git archive` gebaut und auf dem
Zielhost entpackt; der Zielhost braucht dann keinen eigenen GitLab-Zugriff.

Beispiel:

```bash
ansible-playbook -i inventory.yml oeds-update.yml \
  -e oeds_repo_source_mode=local_archive \
  -e oeds_repo_local_src=/mnt/c/Users/js2644/PycharmProjects/oeds \
  -e oeds_repo_version=open_source_public \
  -e oeds_enable_crawlers=true
```

Im Standardmodus `git` pruefen die Playbooks den Repo-Zugriff jetzt ausserdem
vor jedem Downtime-Schritt mit `GIT_TERMINAL_PROMPT=0`. Fehlende Credentials
fuehren damit zu einem schnellen, klaren Fehler statt zu einem haengenden
`git fetch`.

## Installationslevel

Die einfachen Einstiege sind Wrapper-Playbooks. Sie rufen die detaillierten
Playbooks in der richtigen Reihenfolge auf.

### Level 0: lokaler Entwicklerstart

Ohne Ansible, direkt aus dem OEDS-Repo:

```bash
docker compose up -d
```

Mit Crawler-Containern:

```bash
docker compose --profile crawlers up -d --build
```

Das ist der schnellste Weg fuer lokale Tests, aber kein kompletter VM-Setup.

### Level 1: Host vorbereiten

Nur OS-Repos, SELinux-Policy und Pakete installieren:

```bash
ansible-playbook -i inventory.yml oeds-install-host-prep.yml
```

Dieses Level ist fuer neue Linux-Hosts gedacht. Auf Hosts mit bereits
funktionierendem Docker kann es uebersprungen werden.

### Level 2: OEDS Core

Installiert Pakete, Docker-Volumes, Runtime-Verzeichnisse, Repo-Checkout und
startet Datenbank, PostgREST, Grafana und PgAdmin:

```bash
ansible-playbook -i inventory.yml oeds-install-core.yml \
  -e oeds_repo_version=<branch-or-tag>
```

Das ist der empfohlene Minimalpfad fuer einen Server ohne Scheduler und ohne
Crawler-Admin-UI.

Wenn du Portainer trotzdem nutzen willst, starte es danach bewusst als
optionales `ops`-Profil, statt es in jede Core-Installation zu mischen:

```bash
cd /open_energy_data_server/repo
docker compose --profile ops up -d portainer portainer_agent
```

### Level 3: OEDS mit Crawler-Services

Wie Level 2, zusaetzlich mit Scheduler und Crawler-Admin-UI als Container:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_version=<branch-or-tag>
```

Das ist der empfohlene Standardpfad fuer eine laenger laufende OEDS-Instanz.
Die gewaehlte `oeds_repo_version` muss dafuer den Compose-Profileintrag
`crawlers` enthalten.

Erstlauf auf einer sauberen Test-VM:

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

Danach sollte die VM nicht direkt als "vollstaendig befuellt" betrachtet
werden. Auf einem Clean-Setup existieren crawler-abhaengige Schemas und
Dashboard-Inhalte erst nach dem ersten erfolgreichen Crawler-Lauf. Fuer die
Validierung wurde deshalb nach dem Installationslauf mindestens ein manueller
`weather_forecast`-Run ueber die Crawler-Admin-UI ausgefuehrt.

Fuer Produktion sollte `oeds_repo_version` kein bewegliches `latest` sein,
sondern ein Branch, Tag oder Commit, der vorher getestet wurde.

## Update-Prozess

Fuer normale App-, Compose- und Container-Image-Updates:

```bash
ansible-playbook -i inventory.yml oeds-update.yml \
  -e oeds_repo_version=<branch-or-tag> \
  -e oeds_enable_crawlers=true
```

Das Playbook:

- erstellt bei laufender Datenbank ein logisches Backup,
- stoppt alte Compose-Projekte,
- checkt die gewuenschte Repo-Version aus,
- schreibt `.env` mit `OEDS_RUNTIME_DIR`,
- kopiert Grafana-/PgAdmin-/SQL-Provisioning,
- fuehrt `docker compose pull` und `docker compose up -d` aus,
- blockiert versehentliche PostgreSQL-Major-Upgrades.

Optional koennen OS-Pakete gezielt mit aktualisiert werden:

```bash
ansible-playbook -i inventory.yml oeds-update.yml \
  -e oeds_update_docker_packages=true \
  -e oeds_update_nginx=true \
  -e oeds_update_certbot=true
```

Diese Flags sollten bewusst gesetzt werden, nicht dauerhaft per Default.

## PostgreSQL-/TimescaleDB-Migration

Ein PostgreSQL-Major-Upgrade darf nicht durch simples Aendern des Images
passieren. Dafuer ist ein eigener Migrationslauf vorgesehen.

1. Backup erstellen:

```bash
ansible-playbook -i inventory.yml oeds-db-backup.yml
```

2. Migration zuerst nur in Staging wiederherstellen:

```bash
ansible-playbook -i inventory.yml oeds-db-migrate.yml \
  -e oeds_apply_cutover=false
```

3. Staging-Ergebnis pruefen, Logs ansehen, Smoke-Test gegen Ziel pruefen.

4. Cutover erst danach aktivieren:

```bash
ansible-playbook -i inventory.yml oeds-db-migrate.yml \
  -e oeds_apply_cutover=true \
  -e oeds_enable_crawlers_after_cutover=true
```

5. Danach Smoke Test:

```bash
ansible-playbook -i inventory.yml oeds-smoke-test.yml \
  -e oeds_expect_crawler_admin=true
```

## Rollback

Rollback setzt voraus, dass ein alter PostgreSQL-Datenordner als Quelle
existiert, zum Beispiel aus dem Migrationsbackup.

```bash
ansible-playbook -i inventory.yml oeds-db-rollback.yml \
  -e oeds_rollback_source_dir=/open_energy_data_server/backups/<run-id>/postgres-home-pre-cutover \
  -e oeds_enable_crawlers_after_rollback=true
```

## Deinstallation und Test-Reset

Fuer eine vorsichtige Deinstallation ohne Datenverlust:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml
```

Das entfernt Container und Docker-Netzwerke, laesst aber Git-Checkout,
Runtime-Dateien, Backups und Docker-Volumes stehen. Damit kann der Dienst
sauber gestoppt werden, ohne Datenbankdaten oder lokale Config zu loeschen.
Docker selbst, nginx, Firewall-Regeln und Zertifikate werden dabei nicht
entfernt.

Fuer einen frischen Testlauf mit neuem Repo-Checkout:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true
```

Fuer einen kompletten Reset einer Test-VM inklusive Datenbank-Volumes,
Runtime-Config und Repo:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true \
  -e oeds_uninstall_remove_runtime=true \
  -e oeds_uninstall_destroy_data=true \
  -e oeds_uninstall_confirm=DELETE_OEDS_DATA
```

Backups und gecachte Docker-Images bleiben auch dabei standardmaessig erhalten.
Nur wenn sie ebenfalls entfernt werden sollen:

```bash
ansible-playbook -i inventory.yml oeds-uninstall.yml \
  -e oeds_uninstall_remove_repo=true \
  -e oeds_uninstall_remove_runtime=true \
  -e oeds_uninstall_destroy_data=true \
  -e oeds_uninstall_remove_backups=true \
  -e oeds_uninstall_remove_images=true \
  -e oeds_uninstall_confirm=DELETE_OEDS_DATA
```

Danach kann die VM mit einem Installationslevel neu aufgebaut werden, zum
Beispiel:

```bash
ansible-playbook -i inventory.yml oeds-install-crawlers.yml \
  -e oeds_repo_version=<branch-or-tag>
```

## Playbook-Uebersicht

- `oeds-install-host-prep.yml`: Level-1-Wrapper fuer interne VM-Vorbereitung.
- `oeds-install-core.yml`: Level-2-Wrapper fuer OEDS Core ohne Crawler-Services.
- `oeds-install-crawlers.yml`: Level-3-Wrapper fuer Core plus Scheduler und
  Crawler-Admin-UI.
- `oeds-packages.yml`: installiert nginx und Docker/Compose-Pakete.
- `oeds-docker-config.yml`: initialisiert Docker-Volumes, Runtime-Verzeichnisse,
  Repo-Checkout und Compose-Stack.
- `oeds-update.yml`: rollt eine neue Repo-/Compose-/Image-Version aus.
- `oeds-db-backup.yml`: erstellt DB-, Extension-, Compose- und Runtime-Backups.
- `oeds-db-migrate.yml`: migriert PostgreSQL/TimescaleDB per dump/restore in
  einen neuen Zielcontainer und optionalem Cutover.
- `oeds-db-rollback.yml`: setzt den live PostgreSQL-Datenpfad auf einen alten
  Datenstand zurueck.
- `oeds-uninstall.yml`: stoppt und entfernt OEDS-Container/Netzwerke; loescht
  Daten, Runtime, Repo, Backups oder Images nur mit expliziten Flags.
- `oeds-smoke-test.yml`: prueft PostgreSQL, PostgREST, Grafana, PgAdmin und
  optional die Crawler-Admin-UI; HTTP-Endpunkte werden mit Retries geprueft,
  damit frische Grafana-/PgAdmin-Starts nicht als Fehlalarm enden.
- Reverse-Proxy-, TLS- und Firewall-Anpassungen sind bewusst nicht Teil des
  oeffentlichen Standardpfads und sollten hostspezifisch ausserhalb dieses
  Repositories gepflegt werden.

## Repository-Einordnung

Die Playbooks koennen im OEDS-Repo mitgefuehrt werden, solange diese Trennung
eingehalten wird:

- generische Installation, Update, Backup, Migration und Rollback duerfen im
  Repository liegen.
- `inventory.yml`, `group_vars/oeds.yml`, Secrets und lokale Runtime-Dateien
  bleiben unveroeffentlicht.
- KIT-spezifische Playbooks bleiben klar als internes Level markiert.
- Updates laufen ueber getestete Tags, Branches oder Commits, nicht ueber ein
  unkontrolliertes `latest`.

## Validierter Betriebsstand

Der aktuell dokumentierte und gegen eine externe Test-VM verifizierte Stand ist
zusaetzlich in [../docs/source/deployment_validation.md](../docs/source/deployment_validation.md)
beschrieben. Diese Doku deckt die getestete Kombination aus Uninstall,
Neuinstallation, Smoke-Test, Admin-Konfigurationsaenderungen und erstem
manuellen Crawler-Lauf ab.
