# Configuration

Runtime configuration is managed in the NetBox UI:

- `Plugins -> UniFi Sync -> Settings`
- `Plugins -> UniFi Sync -> Controllers`
- `Plugins -> UniFi Sync -> Site mappings`

## Minimum required

1. Create global settings with:
   - `tenant_name`
   - `netbox_roles`
2. Add at least one enabled controller.
3. Add site mappings where UniFi site name differs from NetBox site name.

## Credentials

Set credentials in `Controllers` UI fields (`api_key_ref`, `username_ref`, `password_ref`, `mfa_secret_ref`).
Do not store credentials in `PLUGINS_CONFIG`.

Supported formats for credential fields:

- `env:VAR_NAME` — read from environment variable
- `file:/absolute/path/to/secret` — read from file
- plain value — pasted directly

## Optional bootstrap in PLUGINS_CONFIG

You can pre-seed defaults via `PLUGINS_CONFIG["netbox_unifi_sync"]`, but UI models are the authoritative runtime state.

Reference: [docs/configuration.md](https://github.com/unifi2netbox/netbox-unifi-sync/blob/main/docs/configuration.md)
