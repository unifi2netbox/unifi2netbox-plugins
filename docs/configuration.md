# Configuration Reference

`netbox_unifi_sync` is configured in NetBox UI first.  
`PLUGINS_CONFIG` is optional bootstrap/default input.

## Configuration Layers

1. Plugin UI models (authoritative runtime state):
   - `Settings` (`GlobalSyncSettings`)
   - `Controllers` (`UnifiController`)
   - `Site mappings` (`SiteMapping`)
2. Optional bootstrap defaults from `PLUGINS_CONFIG["netbox_unifi_sync"]`
3. Internal compatibility mapping into legacy engine keys (handled by plugin services)

Credential policy:
- UniFi credentials are read from `Controllers` UI fields only.
- `PLUGINS_CONFIG` should not be used to store UniFi credentials.

## Minimum Required Setup (UI)

Before first sync, set:

- `Settings`:
  - `tenant_name` (required)
  - `netbox_roles` JSON mapping (required)
- `Controllers`:
  - at least one enabled controller
  - `auth_mode` and matching credentials
- `Site mappings`:
  - required when UniFi site names differ from NetBox site names

## Optional `PLUGINS_CONFIG` Bootstrap

You can keep this minimal:

```python
PLUGINS = ["netbox_unifi_sync"]

PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

You can also preseed defaults:

```python
PLUGINS_CONFIG = {
    "netbox_unifi_sync": {
        "verify_ssl": True,
        "default_site": "",
        "dry_run": False,
    }
}
```

## Controller Auth Modes

### `api_key` (recommended)

- Uses Integration API v1
- Requires `api_key_ref` on the controller row
- Optional custom header `api_key_header` (default `X-API-KEY`)

### `login` (legacy fallback)

- Uses username/password session login
- Requires `username_ref` + `password_ref` on the controller row
- Optional `mfa_secret`

Note: local Integration API keys are required for Integration API mode.  
`unifi.ui.com` cloud API keys are not drop-in compatible.

## Key Runtime Settings (UI)

### Sync scope and behavior

- `sync_interfaces`
- `sync_vlans`
- `sync_wlans`
- `sync_cables`
- `sync_stale_cleanup`
- `cleanup_enabled`
- `cleanup_grace_days`
- `dry_run_default`

### IPAM and DHCP

- `dhcp_auto_discover`
- `dhcp_writeback_enabled`
- Prefix sync is enabled by default (`SYNC_PREFIXES=true` internally)
- DHCP scopes are created as NetBox IP Ranges (`SYNC_DHCP_RANGES=true` internally)

### Identity and mapping

- `tenant_name`
- `default_site`
- `tag_strategy`
- `default_tags`
- `asset_tag_enabled`
- `asset_tag_patterns`
- `asset_tag_uppercase`
- `netbox_roles` JSON mapping

### VRF and serial strategy

- `vrf_mode`: `none` | `existing` | `create`
- `default_vrf_name`
- `serial_mode`: `mac` | `unifi` | `id` | `none`

### Reliability and concurrency

- `verify_ssl_default`
- `request_timeout`
- `http_retries`
- `retry_backoff_base`
- `retry_backoff_max`
- `max_controller_threads`
- `max_site_threads`
- `max_device_threads`
- `rate_limit_per_second`

### Specs refresh (optional)

- `specs_auto_refresh`
- `specs_include_store`
- `specs_refresh_timeout`
- `specs_store_timeout`
- `specs_store_max_workers`
- `specs_write_cache`

## Advanced: Engine Key Reference

The plugin maps UI state into these internal engine keys (for compatibility/debugging):

| Internal key | Source in plugin UI |
|---|---|
| `UNIFI_URLS` | Enabled controller URLs (`base_url`) |
| `UNIFI_API_KEY` | `api_key_ref` |
| `UNIFI_API_KEY_HEADER` | `api_key_header` |
| `UNIFI_USERNAME` | `username_ref` |
| `UNIFI_PASSWORD` | `password_ref` |
| `UNIFI_MFA_SECRET` | `mfa_secret_ref` |
| `UNIFI_VERIFY_SSL` | controller `verify_ssl` or global default |
| `UNIFI_REQUEST_TIMEOUT` | `request_timeout` |
| `UNIFI_HTTP_RETRIES` | `http_retries` |
| `UNIFI_RETRY_BACKOFF_BASE` | `retry_backoff_base` |
| `UNIFI_RETRY_BACKOFF_MAX` | `retry_backoff_max` |
| `NETBOX_IMPORT_TENANT` | `tenant_name` |
| `NETBOX_DEFAULT_VRF` | `default_vrf_name` |
| `NETBOX_VRF_MODE` | `vrf_mode` |
| `NETBOX_SERIAL_MODE` | `serial_mode` |
| `UNIFI_SITE_MAPPINGS` | `Site mappings` model rows |
| `UNIFI_TAG_STRATEGY` | `tag_strategy` |
| `SYNC_INTERFACES` | `sync_interfaces` |
| `SYNC_VLANS` | `sync_vlans` |
| `SYNC_WLANS` | `sync_wlans` |
| `SYNC_CABLES` | `sync_cables` |
| `SYNC_STALE_CLEANUP` | `sync_stale_cleanup` |
| `SYNC_PREFIXES` | Enabled internally (default `true`) |
| `SYNC_DHCP_RANGES` | Enabled internally (default `true`) |
| `DHCP_AUTO_DISCOVER` | `dhcp_auto_discover` |
| `NETBOX_CLEANUP` | `cleanup_enabled` |
| `CLEANUP_STALE_DAYS` | `cleanup_grace_days` |

## Advanced: Optional Bootstrap Keys

These are valid in `PLUGINS_CONFIG["netbox_unifi_sync"]` when you need preseed defaults:

- `unifi_url` or `unifi_urls`
- `verify_ssl`
- `default_site`
- `dry_run`
- `netbox_import_tenant`, `netbox_roles`
- `unifi_site_mappings`
- `tag_strategy`, `default_tags`
- `asset_tag_enabled`, `asset_tag_patterns`, `asset_tag_uppercase`
- `rate_limit_per_second`

## Secret Handling

Credentials are set in `Controllers` UI fields (`api_key_ref`, `username_ref`, `password_ref`, `mfa_secret_ref`).
Supported formats in those controller fields:

- `env:VAR_NAME`
- `file:/absolute/path/to/secret`
- direct pasted credential value

## Advanced Compatibility Notes

- The sync engine still consumes environment-style keys internally.
- Plugin services map UI state into those keys at runtime.
- You normally do not need to set `NETBOX_URL`/`NETBOX_TOKEN` manually in plugin mode.
- Legacy CLI/standalone configuration is not required for normal plugin operation.
