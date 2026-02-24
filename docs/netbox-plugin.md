# NetBox Plugin Mode

This project includes a native NetBox plugin package: `netbox_unifi2netbox`.

## Install

Install into the same Python environment as NetBox:

```bash
pip install /path/to/unifi2netbox-plugins
```

Enable it in `configuration.py`:

```python
PLUGINS = ["netbox_unifi2netbox"]

PLUGINS_CONFIG = {
    "netbox_unifi2netbox": {
        "unifi_urls": ["https://controller.example.com/proxy/network/integration/v1"],
        "unifi_api_key": "your-unifi-api-key",
        "netbox_url": "https://netbox.example.com",
        "netbox_token": "your-netbox-api-token",
        "netbox_import_tenant": "Organization Name",
        "netbox_roles": {
            "WIRELESS": "Wireless AP",
            "LAN": "Switch",
            "GATEWAY": "Gateway Firewall",
            "ROUTER": "Router",
            "UNKNOWN": "Network Device"
        },
        "sync_interval_minutes": 0,
    }
}
```

Restart NetBox services after configuration changes.

## Job behavior

- `Unifi2NetBoxSyncJob` always runs a single sync cycle (`SYNC_INTERVAL=0`).
- If `sync_interval_minutes > 0`, a system job (`Unifi2NetBoxScheduledSyncJob`) is registered automatically with that interval.
- Most existing environment variables can still be set through plugin settings and are translated internally.
- `extra_env` can pass through unsupported/advanced env vars as raw key/value pairs.

## Important constraint

The current sync engine still uses API access to NetBox (`netbox_url` + `netbox_token`) internally.
So, even when running as a plugin inside NetBox, these settings must be provided.
