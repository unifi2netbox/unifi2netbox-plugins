# Configuration

Runtime-konfiguration håndteres primært i NetBox UI:

- `Plugins -> UniFi Sync -> Settings`
- `Plugins -> UniFi Sync -> Controllers`
- `Plugins -> UniFi Sync -> Site mappings`

## Minimum required

1. Opret global settings med:
   - `tenant_name`
   - `netbox_roles`
2. Opret mindst én aktiv controller.
3. Opret site mappings hvor UniFi site-navn != NetBox site-navn.

## Credentials

Sæt credentials i `Controllers` UI felterne (`api_key_ref`, `username_ref`, `password_ref`, `mfa_secret_ref`).
Undgå at lægge credentials i `PLUGINS_CONFIG`.

## Optional bootstrap in PLUGINS_CONFIG

Du kan stadig pre-seede defaults via `PLUGINS_CONFIG["netbox_unifi_sync"]`, men UI-modeller er autoritativ runtime state.

Reference: [docs/configuration.md](https://github.com/unifi2netbox/netbox-unifi-sync/blob/main/docs/configuration.md)
