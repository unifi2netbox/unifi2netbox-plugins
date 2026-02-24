# NetBox Docker Test Setup (`netbox_unifi_sync`)

This folder contains a reproducible `netbox-docker` setup for local plugin testing.

## 1) Clone repositories

```bash
git clone https://github.com/patricklind/unifi2netbox.git
cd unifi2netbox
git clone -b release https://github.com/netbox-community/netbox-docker.git .netbox-docker
```

## 2) Copy override + plugin config

```bash
cp deploy/netbox-docker/docker-compose.override.yml .netbox-docker/docker-compose.override.yml
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
```

`netbox-docker` loads `.netbox-docker/configuration/plugins.py` from
`/opt/netbox/netbox/netbox/configuration.py` at runtime.

## 3) Configure environment variables

```bash
cp deploy/netbox-docker/env.netbox-plugin.example .netbox-docker/.env.plugin
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

## 5) Create superuser

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

## 6) Test plugin

1. Open `http://localhost:8000`
2. Login as superuser
3. Go to `Plugins -> NetBox UniFi Sync -> Settings`
4. Configure global settings + controllers
5. Run dry-run from dashboard

## 7) Optional CLI test

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py netbox_unifi_sync_run --dry-run --json
```
