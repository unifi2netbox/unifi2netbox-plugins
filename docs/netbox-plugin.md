# NetBox Plugin Mode

`unifi2netbox` now ships as an installable NetBox plugin package: `netbox_unifi2netbox`.

## What changed

- Sync execution is now plugin-native and can run from NetBox background Jobs.
- Runtime settings are sourced from `PLUGINS_CONFIG["netbox_unifi2netbox"]`.
- Sync history is stored in a plugin model (`SyncRun`) for status/error tracking.
- A management command (`unifi2netbox_sync`) is available for CLI runs from NetBox.

## Installation

From your NetBox Python environment:

```bash
pip install /path/to/unifi2netbox
```

For development (editable):

```bash
pip install -e /path/to/unifi2netbox
```

## NetBox configuration

In `configuration.py`:

```python
PLUGINS = ["netbox_unifi2netbox"]

PLUGINS_CONFIG = {
    "netbox_unifi2netbox": {
        "unifi_urls": ["https://controller.example.com/proxy/network/integration/v1"],

        # Credentials (plain value or env/file reference)
        #   "env:UNIFI_API_KEY" or "file:/run/secrets/unifi_api_key"
        "unifi_api_key": "env:UNIFI_API_KEY",
        "unifi_api_key_header": "X-API-KEY",
        # Alternative login mode:
        "unifi_username": "",
        "unifi_password": "",
        "unifi_mfa_secret": "",

        "netbox_url": "https://netbox.example.com",
        "netbox_token": "env:NETBOX_TOKEN",

        # Tenant (import wins if both are set)
        "netbox_import_tenant": "Organization Name",
        "netbox_tenant": "",

        "netbox_roles": {
            "WIRELESS": "Wireless AP",
            "LAN": "Switch",
            "GATEWAY": "Gateway Firewall",
            "ROUTER": "Router",
            "UNKNOWN": "Network Device",
        },

        # Optional behavior
        "unifi_site_mappings": {"UniFi Site": "NetBox Site"},
        "default_site_name": "",
        "tag_strategy": "append",  # append | replace | none
        "default_tags": ["unifi", "managed"],
        "dry_run_default": False,

        "sync_interfaces": True,
        "sync_vlans": True,
        "sync_wlans": True,
        "sync_cables": True,
        "sync_stale_cleanup": True,
        "netbox_cleanup": False,
        "cleanup_stale_days": 30,

        "unifi_verify_ssl": True,
        "netbox_verify_ssl": True,

        # Register recurring system job every N minutes (0 disables schedule)
        "sync_interval_minutes": 0,

        # Optional raw pass-through env overrides for advanced flags
        "extra_env": {
            # "UNIFI_SPECS_AUTO_REFRESH": "true",
            # "UNIFI_SPECS_INCLUDE_STORE": "false",
        },
    }
}
```

Restart NetBox services after config changes.

## Running sync

### Manual from UI

- Go to plugin page: `Plugins > UniFi Sync Status`
- Click **Queue sync job**
- Or run the job from NetBox Jobs UI.

### Scheduled

Set `sync_interval_minutes` to a value > 0 in plugin config.

### CLI

```bash
python manage.py unifi2netbox_sync
python manage.py unifi2netbox_sync --dry-run
python manage.py unifi2netbox_sync --json
```

## UI pages

- `Plugins > UniFi Sync Status` - current status + queue button + sanitized effective config
- `Plugins > Sync Runs` - run history and filtering
- Run detail page - full payload, snapshot, and errors

## Permissions

Model permissions on `SyncRun` control access:

- `netbox_unifi2netbox.view_syncrun` - view status/history pages
- `netbox_unifi2netbox.run_sync` - queue new runs

## Dry-run behavior

`dry_run=True` performs a preflight validation:

- NetBox API reachability (`/api/status/`)
- UniFi controller authentication and site discovery

No synchronization writes are performed in dry-run mode.
