# NetBox Docker Test Setup (`netbox_unifi_sync`)

This folder contains a reproducible `netbox-docker` setup for local plugin validation.

## 1) Clone repositories

```bash
git clone https://github.com/unifi2netbox/netbox-unifi-sync.git
cd netbox-unifi-sync
git clone -b release https://github.com/netbox-community/netbox-docker.git .netbox-docker
```

## 2) Recommended: install via `local_requirements.txt`

Add package pin and plugin config:

```bash
echo "netbox-unifi-sync" >> .netbox-docker/local_requirements.txt
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
```

Build and start:

```bash
cd .netbox-docker
docker compose build netbox netbox-worker
docker compose up -d
docker compose ps
```

## 3) Alternative dev mode: editable mount install

Use this when testing local code changes live (without rebuilding image):

```bash
cp deploy/netbox-docker/docker-compose.override.yml .netbox-docker/docker-compose.override.yml
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
```

`plugins.py` is imported by NetBox runtime and enables `netbox_unifi_sync`.

## 4) Configure plugin path env

```bash
cp deploy/netbox-docker/env.netbox-plugin.example .netbox-docker/.env.plugin
```

Edit `.netbox-docker/.env.plugin` and set absolute path:

```bash
UNIFI2NETBOX_PLUGIN_PATH=/absolute/path/to/netbox-unifi-sync
```

Load vars into `netbox-docker` env:

```bash
set -a
source .netbox-docker/.env.plugin
set +a
cat .netbox-docker/.env.plugin >> .netbox-docker/env/netbox.env
```

## 5) Start stack

```bash
cd .netbox-docker
docker compose pull
docker compose up -d
docker compose ps
```

## 6) Run migrations

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py migrate
```

## 7) Create superuser

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

## 8) Validate plugin

- Open `http://localhost:8000`
- Login as superuser
- Open `Plugins -> UniFi Sync -> Settings`
- Add required settings + controller
- Run dry-run, then full sync

CLI validation:

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py netbox_unifi_sync_run --dry-run --json
```

## Notes

- In recommended mode, plugin is installed from `local_requirements.txt` during image build.
- In dev mode, both `netbox` and `netbox-worker` install plugin via editable mode at container startup.
- Startup install is guarded: if `UNIFI2NETBOX_PLUGIN_PATH` does not point to a Python project (`pyproject.toml` or `setup.py`), installation is skipped instead of crashing NetBox startup.
- If plugin code changes, restart both services:

```bash
docker compose restart netbox netbox-worker
```
