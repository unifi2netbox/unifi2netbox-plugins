# NetBox Plugin Mode

This project ships as a NetBox plugin package named `netbox_unifi_sync`.

## Install

From your NetBox Python environment:

```bash
pip install netbox-unifi-sync
```

For development (editable):

```bash
pip install -e /path/to/netbox-unifi-sync
```

## NetBox configuration

In `configuration.py`:

```python
PLUGINS = ["netbox_unifi_sync"]

PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

Runtime configuration is managed in NetBox UI (`Plugins -> UniFi Sync`).

## Run sync

- UI: `Plugins -> UniFi Sync -> Sync Dashboard -> Run now`
- CLI:

```bash
python manage.py netbox_unifi_sync_run --dry-run --json
python manage.py netbox_unifi_sync_run --cleanup
```

## Permissions

- `netbox_unifi_sync.run_sync`
- `netbox_unifi_sync.run_cleanup`
- `netbox_unifi_sync.test_controller`
