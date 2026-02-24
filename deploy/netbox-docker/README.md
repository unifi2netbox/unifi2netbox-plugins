# NetBox Docker Test Setup (`netbox_unifi_sync`)

This folder contains a reproducible `netbox-docker` setup for local plugin validation.

## 1) Clone repositories

```bash
git clone https://github.com/unifi2netbox/unifi2netbox-plugins.git
cd unifi2netbox-plugins
git clone -b release https://github.com/netbox-community/netbox-docker.git .netbox-docker
```

## 2) Copy override + plugin config

```bash
cp deploy/netbox-docker/docker-compose.override.yml .netbox-docker/docker-compose.override.yml
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
```

`plugins.py` is imported by NetBox runtime and enables `netbox_unifi_sync`.

## 3) Configure plugin path env

```bash
cp deploy/netbox-docker/env.netbox-plugin.example .netbox-docker/.env.plugin
```

Edit `.netbox-docker/.env.plugin` and set absolute path:

```bash
UNIFI2NETBOX_PLUGIN_PATH=/absolute/path/to/unifi2netbox-plugins
```

Load vars into `netbox-docker` env:

```bash
set -a
source .netbox-docker/.env.plugin
set +a
cat .netbox-docker/.env.plugin >> .netbox-docker/env/netbox.env
```

## 4) Start stack

```bash
cd .netbox-docker
docker compose pull
docker compose up -d
docker compose ps
```

## 5) Run migrations

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py migrate
```

## 6) Create superuser

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

## 7) Validate plugin

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

- Both `netbox` and `netbox-worker` install plugin via editable mode at container startup.
- If plugin code changes, restart both services:

```bash
docker compose restart netbox netbox-worker
```
