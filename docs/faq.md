# Frequently Asked Questions

## General

### Does plugin sync write back to UniFi?

Primarily no. Normal direction is **UniFi -> NetBox**.  
Writeback happens only for DHCP-to-static flow when `dhcp_writeback_enabled` is enabled.

### Which UniFi API mode should I use?

Use `api_key` mode when possible (Integration API v1).  
Use `login` mode only when Integration API is not available.

### Can I use `unifi.ui.com` cloud API keys?

Not as a direct replacement for local Integration API keys.

### Can I use multiple controllers?

Yes. Add multiple enabled controllers in `Plugins -> UniFi Sync -> Controllers`.

### Can I run sync manually from UI?

Yes. Open `Plugins -> UniFi Sync -> Sync Dashboard` and use `Run now`.

## Data and Mapping

### What if UniFi site names differ from NetBox site names?

Use `Site mappings` in plugin UI. You can set global mappings or controller-specific mappings.

### Are prefixes created automatically?

Yes. Prefix sync is enabled by default (same strategy as VLAN sync).  
If a UniFi subnet is missing in NetBox, prefix is created.

### Are DHCP scopes visible in NetBox IP Ranges?

Yes. UniFi DHCP pools are synced as NetBox IP Ranges under matching prefixes.

### What happens to device status?

- On create: default status is `planned` (unless overridden)
- On update: status is not force-reset to `planned`

### What happens to offline devices?

If `sync_stale_cleanup` is enabled, stale devices can be marked offline.  
If `cleanup_enabled` is enabled, stale devices can be deleted after `cleanup_grace_days`.

## Security and Credentials

### Where should I place credentials?

Set credentials only in `Plugins -> UniFi Sync -> Controllers`.
Accepted values in controller credential fields:

- `env:VAR_NAME`
- `file:/absolute/path/to/secret`
- direct pasted credential value

Do not store UniFi credentials in `PLUGINS_CONFIG`.

### Is SSL verification enabled by default?

Yes. SSL verification defaults to `true`.

## Operations

### How do I run a dry-run?

- UI: enable dry-run on dashboard action form
- CLI: `python manage.py netbox_unifi_sync_run --dry-run --json`

### How do I run cleanup?

- UI: request cleanup from dashboard action form
- CLI: `python manage.py netbox_unifi_sync_run --cleanup`

### How do I troubleshoot missing data?

1. Test controller connection in `Controllers`.
2. Validate `tenant_name` and `netbox_roles` in `Settings`.
3. Validate `Site mappings`.
4. Inspect latest run details and worker logs.
