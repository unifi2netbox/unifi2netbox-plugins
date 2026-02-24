# netbox_unifi_sync

`netbox_unifi_sync` is a NetBox 4.2+ plugin that runs UniFi -> NetBox sync jobs **inside NetBox** using background workers.

## Highlights

- Plugin name: `netbox_unifi_sync`
- No external sync service required
- Controller inventory sync (devices/interfaces/VLAN/WLAN/uplinks/IP data)
- Optional cleanup flow
- Optional DHCP writeback feature flag
- Job-based execution (manual + scheduled)
- Database-backed plugin settings (single source of truth)

## Install

```bash
pip install .
# or editable for development
pip install -e .
```

## Enable plugin

```python
PLUGINS = ["netbox_unifi_sync"]
PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

## First-time setup in UI

1. Open `Plugins -> NetBox UniFi Sync -> Settings`
2. Set required global settings (`tenant_name`, `netbox_roles`, runtime/security values)
3. Add one or more controllers in `Controllers`
4. Use secret references (`env:VAR_NAME` or `file:/path`) for credentials
5. Run a `Dry run` from the dashboard

## Authentication modes

- `api_key`: uses UniFi Integration API header auth
- `login`: uses username/password (+ optional MFA secret)

## Management command

```bash
python manage.py netbox_unifi_sync_run --dry-run --json
python manage.py netbox_unifi_sync_run --cleanup
```

## Docker test

See [deploy/netbox-docker/README.md](deploy/netbox-docker/README.md).

## Security notes

- Secrets should be provided as references (`env:` / `file:`), not plaintext
- Error messages are sanitized before persistence
- SSL verification is enabled by default
- Timeouts and retry/backoff are configurable

## Legacy packages

This repository still contains legacy `unifi2netbox`/`netbox_unifi2netbox` modules for backward compatibility while migration to `netbox_unifi_sync` completes.
