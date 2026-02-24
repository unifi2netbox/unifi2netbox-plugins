# netbox_unifi_sync

`netbox_unifi_sync` is a NetBox 4.2+ plugin for running UniFi -> NetBox sync jobs inside NetBox workers.

## What it does

- Syncs UniFi devices into NetBox (devices, interfaces, VLANs, prefixes, WLANs, uplink relations, IP assignments)
- Creates DHCP scopes as NetBox IP Ranges
- Supports UniFi auth via API key or login (username/password + optional MFA)
- Runs as NetBox jobs (manual run + scheduler job)
- Stores operational settings in plugin models (UI/DB). `PLUGINS_CONFIG` is optional bootstrap only.

## Canonical plugin name

Use:

```python
PLUGINS = ["netbox_unifi_sync"]
```

## Install from PyPI

```bash
pip install netbox-unifi-sync
```

## Install on a NetBox server (venv)

1. Clone repository:

```bash
git clone https://github.com/unifi2netbox/unifi2netbox-plugins.git
cd unifi2netbox-plugins
```

2. Install plugin in NetBox venv:

```bash
/opt/netbox/venv/bin/pip install -e /path/to/unifi2netbox-plugins
```

3. Enable plugin in NetBox `configuration.py`:

```python
PLUGINS = ["netbox_unifi_sync"]

PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

Configure tenant, controllers, credentials, mappings, and sync behavior in NetBox UI under `Plugins -> UniFi Sync`.

4. Run migrations:

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate
```

5. Restart NetBox services (web + worker).

## Install with netbox-docker

See detailed instructions in:

- [deploy/netbox-docker/README.md](deploy/netbox-docker/README.md)
- [docs/server-install.md](docs/server-install.md)

## First-time setup in UI

1. Open `Plugins -> UniFi Sync -> Settings`
2. Set required global settings (`tenant_name`, role mappings, defaults)
3. Add one or more controllers in `Controllers`
4. Add site mappings in `Site mappings` (required if UniFi site names differ from NetBox site names)
5. Run a dry-run from dashboard, then run full sync

## Run commands

```bash
python manage.py netbox_unifi_sync_run --dry-run --json
python manage.py netbox_unifi_sync_run --cleanup
```

## Authentication

- `api_key`: Integration API header auth
- `login`: username/password (+ optional MFA secret)

Store credentials as secret references (`env:VAR` or `file:/path`) instead of plaintext.

## Documentation

- [Server install guide](docs/server-install.md)
- [NetBox plugin mode](docs/netbox-plugin.md)
- [Configuration details](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)

## Security notes

- SSL verification defaults to `true`
- Secrets are redacted in run history and audit events
- Timeouts/retry/backoff are configurable

## Maintainer release to PyPI

1. Bump version in:
   - `pyproject.toml` -> `[project].version`
   - `netbox_unifi_sync/version.py` -> `__version__`
2. Push to `main`. Auto-tag workflow creates `v<version>` from `pyproject.toml`.
3. Ensure GitHub secret `PYPI_API_TOKEN` is set in repository settings.
4. On tag push, `release.yml` builds, validates, and publishes to PyPI.
