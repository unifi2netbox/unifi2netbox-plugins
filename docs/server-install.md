# Server Installation Guide

This guide describes how to install `netbox_unifi_sync` on a real NetBox server.

## Prerequisites

- NetBox `4.2+`
- Python `3.11+` (plugin runtime tested on 3.12)
- Access to NetBox venv or netbox-docker containers
- Existing NetBox tenant for imports
- UniFi controller reachable from NetBox worker

## Option A: NetBox in venv (system install)

### 1. Install from PyPI

```bash
/opt/netbox/venv/bin/pip install netbox-unifi-sync
```

PyPI project:
<https://pypi.org/project/netbox-unifi-sync/>

For local development (editable install from source):

```bash
git clone https://github.com/unifi2netbox/netbox-unifi-sync.git
/opt/netbox/venv/bin/pip install -e /path/to/netbox-unifi-sync
```

### 2. Configure NetBox

Edit `/opt/netbox/netbox/netbox/configuration.py`:

```python
PLUGINS = ["netbox_unifi_sync"]

PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

### 3. Run migrations

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate
```

### 4. Restart NetBox services

Restart both web and worker services (exact service names depend on your deployment).

### 5. Verify plugin load

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py check
```

Then open NetBox UI and verify `Plugins -> UniFi Sync` exists.

## Option B: netbox-docker

### 1. Clone repos

```bash
git clone https://github.com/unifi2netbox/netbox-unifi-sync.git
cd netbox-unifi-sync
git clone -b release https://github.com/netbox-community/netbox-docker.git .netbox-docker
```

### 2. (Recommended) Install via `local_requirements.txt`

Add package pin in `netbox-docker` root:

```bash
echo "netbox-unifi-sync" >> .netbox-docker/local_requirements.txt
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
```

Build and start:

```bash
cd .netbox-docker
docker compose build netbox netbox-worker
docker compose up -d
```

### 3. (Development) Editable mount install with override

```bash
cp deploy/netbox-docker/docker-compose.override.yml .netbox-docker/docker-compose.override.yml
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
```

### 4. Configure plugin mount path env

```bash
cp deploy/netbox-docker/env.netbox-plugin.example .netbox-docker/.env.plugin
```

Set `UNIFI2NETBOX_PLUGIN_PATH` in `.netbox-docker/.env.plugin` to the absolute path of this repository.

### 5. Export env to netbox-docker

```bash
set -a
source .netbox-docker/.env.plugin
set +a
cat .netbox-docker/.env.plugin >> .netbox-docker/env/netbox.env
```

### 6. Start stack

```bash
cd .netbox-docker
docker compose pull
docker compose up -d
```

The override installs plugin into both `netbox` and `netbox-worker` containers using editable install.

### 7. Run migrations

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py migrate
```

### 8. Validate

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py netbox_unifi_sync_run --dry-run --json
```

## Runtime configuration model

There are two layers:

1. `PLUGINS_CONFIG["netbox_unifi_sync"]`: optional bootstrap/default values.
2. Plugin UI models (authoritative runtime state):
   - Global settings
   - Controllers
   - Site mappings

In practice, configure runtime values in plugin UI. `PLUGINS_CONFIG` is not required for normal operation.
UniFi credentials should be stored only in `Controllers` UI entries.

## Minimum UI setup before first sync

1. `Settings`:
   - `tenant_name` (required)
   - `netbox_roles` mapping (required)
2. `Controllers`:
   - Add at least one enabled controller
   - Set auth mode and credentials in the controller row (`api_key_ref` or `username_ref`/`password_ref`)
3. `Site mappings`:
   - Add mapping rows where UniFi site name differs from NetBox site name

## Post-install smoke test checklist

- Plugin menu is visible in NetBox UI
- Controller test passes
- Dry run finishes without auth/config errors
- Full run creates/updates devices
- Prefixes and DHCP IP Ranges appear in IPAM

## Upgrade workflow

From PyPI install:

```bash
/opt/netbox/venv/bin/pip install --upgrade netbox-unifi-sync
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate
# restart web + worker
```

From source checkout:

```bash
cd /path/to/netbox-unifi-sync
git pull
/opt/netbox/venv/bin/pip install -e .
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate
# restart web + worker
```

For netbox-docker, redeploy containers after pulling latest code.
