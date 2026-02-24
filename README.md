# unifi2netbox

`unifi2netbox` is a **NetBox plugin** for synchronizing UniFi inventory into NetBox.

This repository is now plugin-only. Legacy standalone runtime/deployment artifacts have been removed.

## Install (pip)

```bash
pip install .
# or editable for development
pip install -e .
```

## Enable in NetBox

Use plugin module name `unifi2netbox`.

```python
PLUGINS = ["unifi2netbox"]

PLUGINS_CONFIG = {
    "unifi2netbox": {
        "unifi_url": "https://unifi.local",
        "auth_mode": "api_key",  # or "login"
        "api_key": "env:UNIFI_API_KEY",
        "username": "env:UNIFI_USERNAME",
        "password": "env:UNIFI_PASSWORD",
        "verify_ssl": True,
        "default_site": "",
        "dry_run": False,

        "netbox_url": "http://netbox:8080",
        "netbox_token": "env:NETBOX_TOKEN",
        "netbox_import_tenant": "Default",
        "netbox_roles": {
            "WIRELESS": "Wireless AP",
            "ROUTER": "Router",
            "SWITCH": "Switch",
            "SECURITY": "Security Appliance",
            "PHONE": "VoIP Phone",
            "OTHER": "Network Device"
        }
    }
}
```

## Auth modes

- `auth_mode = "api_key"`
  - Requires `api_key`.
  - Uses header-based UniFi Integration API auth.
  - No fallback to login.
- `auth_mode = "login"`
  - Requires `username` + `password`.
  - Uses UniFi session login flow.

## Run sync

From NetBox UI:

- `Plugins -> UniFi Sync Status`
- Trigger a dry-run first, then full sync.

From NetBox CLI:

```bash
python manage.py unifi2netbox_sync --dry-run
python manage.py unifi2netbox_sync
```

## NetBox Docker test setup

A ready-to-use setup is included under:

- `deploy/netbox-docker/docker-compose.override.yml`
- `deploy/netbox-docker/configuration/plugins.py`
- `deploy/netbox-docker/README.md`

This setup mounts the local plugin under:

- `/plugins/unifi2netbox`
- `/opt/netbox/netbox/plugins/unifi2netbox`

and installs it in containers with:

```bash
uv pip install --python /opt/netbox/venv/bin/python -e /plugins/unifi2netbox
```

## Development

Run tests:

```bash
pytest -q
```

Build package artifacts:

```bash
python -m build
```

## License

MIT
