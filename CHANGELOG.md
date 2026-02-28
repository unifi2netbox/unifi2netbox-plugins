# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [0.3.15] - 2026-02-28

### Added — **MAC address sync (NetBox 4.5 compatible)**

MAC addresses from UniFi devices are now synced to NetBox interface objects.

- NetBox 4.5 uses a dedicated `MACAddress` model (not `Interface.mac_address`) — implemented correctly via `get_or_create` + `primary_mac_address` OneToOneField using `queryset.update()` to bypass `Interface.clean()` validation.
- **Legacy API controllers:** per-port MAC address from `port_table` is set on each interface individually.
- **Integration API controllers:** only a device-level base MAC is available; it is assigned to Port 1.

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/services/sync_engine.py` | New `_set_interface_mac()` helper; port loop sets per-port MAC; device-MAC fallback to Port 1 |

---

## [0.3.14] - 2026-02-28

### Fixed — **Integration API does not support static IP configuration**

`set_unifi_device_static_ip` previously attempted `PATCH /sites/{id}/devices/{id}` via the Integration API, which returns **405 Method Not Allowed**.

The Integration API path is now skipped entirely; the function falls through directly to the Legacy API (`PUT /api/s/{site}/rest/device/{id}`) which supports static IP configuration.

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/services/sync/ipam.py` | Removed Integration API PATCH attempt; always use Legacy API for static IP |

---

## [0.3.13] - 2026-02-28

### Fixed — **Security Appliance primary IP (WAN vs LAN) + VPN filter + dedup**

Three related fixes for Security Appliance (UCG Ultra / UDM / USG) sync:

**Primary IP fallback:**
UniFi Integration API reports the WAN IP as `ipAddress` for gateways, so the `primary_ip4` match (`gateway_ip == device_ip`) never fires for LAN-managed appliances. A new `first_private_ip` fallback tracks the first non-WAN private gateway IP encountered in the network config loop; if `primary_ip4` is still unset after the loop, it is assigned this LAN IP.

**VPN network filter:**
Legacy API network configs include VPN tunnel entries (`purpose: vpn-client / remote-user-vpn / site-vpn / openvpn`) which previously created spurious IPs (e.g. `10.13.13.x/32`) on the `mgmt` interface. These purposes are now skipped.

**Deduplication:**
When merging Integration API + Legacy API network configs the same network could appear twice. Records are now deduplicated by `(name, purpose, vlanId)` before processing.

**Removed — untagged_vlan on virtual gateway interfaces:**
NetBox's `Interface.clean()` rejects `untagged_vlan` for non-access-mode interfaces. Virtual gateway VLAN interfaces (e.g. `vlan10`) do not need this link anyway — their name and IP address already identify the VLAN unambiguously.

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/services/sync_engine.py` | `first_private_ip` fallback; VPN purpose filter; `(name,purpose,vlanId)` dedup; removed `untagged_vlan` assignment |

---

## [0.3.12] - 2026-02-28

### Fixed — **Security Appliance VLAN interfaces and IPs missing with Integration API**

`sync_gateway_interfaces()` only fetched network configs from the Integration API (`site_obj.network_conf.all()`).  The Integration API omits `ip_subnet` / `gateway_ip` fields for many network entries, so no VLAN subinterfaces or IPs were created for Security Appliances when the controller used the Integration API.

**Fix:** Added the same Legacy API fallback used by `sync_site_prefixes`: `_fetch_legacy_networkconf(unifi, site_obj)` is now called when a `unifi` session is available, and the results are merged with the Integration API results.

`sync_gateway_interfaces` now accepts an optional `unifi=` keyword argument; the call site passes the active session.

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/services/sync_engine.py` | `sync_gateway_interfaces(unifi=None)` parameter; legacy networkconf fallback; updated call site |

---

## [0.3.11] - 2026-02-27

### Added — **Client IP sync + Security Appliance interface sync**

- Client IP addresses from UniFi are now synced to NetBox.
- Security Appliance (GATEWAY role) interfaces are correctly created with names, types, and IP assignments.

---

## [0.3.10] - 2026-02-27

### Added — **NetBox Change Log integration**

All sync operations (create / update / delete) are now written to NetBox's built-in Change Log via `ChangeLoggingMixin`.

---

## [0.3.9] - 2026-02-27

### Changed — Version bump

---

## [0.3.8] - 2026-02-27

### Fixed — **Audit log bugs + complete interface/VLAN/WLAN/cable/IP sync**

- Incorrect role assigned to some devices.
- `interface` was `None` in some code paths — NoneType crash.
- WLAN passphrase handled incorrectly in audit log.
- Interface sync: all types (ethernet, SFP, WiFi) synced correctly.
- VLAN sync: VLAN groups and VLAN ID matching corrected.
- WLAN sync: SSIDs and security settings synced.
- Cable sync: cables created with correct terminations.
- IP sync: primary IP assigned to correct interface.
- UniFi Integration API v1 gateway port field normalization — avoids `KeyError` on missing port data.

---

## [0.3.7] - 2026-02-27

### Fixed — **16 Bandit CI errors + cable sync bugs + 5 ORM compatibility errors**

- B607 (start process with partial path), misplaced docstring, and other Bandit static-analysis warnings.
- `_ChoiceValue` wrapper for cable-type choices.
- `get()` positional PK error in cable termination.
- Field name `last_updated` used incorrectly in `update_fields`.
- ORM fields aligned to NetBox 4.x naming conventions.

---

## [0.3.6] - 2026-02-27

### Changed — Version bump

---

## [0.3.5] - 2026-02-27

### Changed — **Refactor: consolidate `unifi2netbox/` into `netbox_unifi_sync/`**

The separate `unifi2netbox/` package has been removed. All sync logic is now consolidated under `netbox_unifi_sync/services/`, simplifying imports and deployment.

---

## [0.3.4] - 2026-02-27

### Changed — **CI: publish to PyPI directly from release workflow**

---

## [0.3.3] - 2026-02-27

### Changed — **Canonical role keys migration**

Old role keys (`SWITCH`, `SECURITY`, `OTHER`, `PHONE`) are automatically migrated to the canonical set (`WIRELESS`, `LAN`, `GATEWAY`, `ROUTER`, `UNKNOWN`) via `_migrate_role_keys()` which runs at plugin startup.

---

## [0.3.2] - 2026-02-26

### Fixed — **TemplateSyntaxError in settings.html**

Removed Jinja2 macro blocks from `settings.html` — NetBox uses Django templates, not Jinja2.

---

## [0.3.1] - 2026-02-26

### Fixed — **ORM adapter IP assignment**

`assigned_object_type` and `primary_ip4` are now set correctly on VirtualMachine and Device objects.

---

## [0.3.0] - 2026-02-26

### Changed — **ChangeLoggingMixin added to key models**

`GlobalSyncSettings`, `UnifiController`, `SiteMapping`, and `SyncRun` now integrate with NetBox's Change Log.

---

## [0.2.9] - 2026-02-26

### Fixed — **Protect Front Port / Rear Port cables from sync overwrite**

Cables on patch-panel ports are no longer overwritten by sync.

---

## [0.2.8] - 2026-02-26

### Added — **Register plugin models as NetBox ObjectTypes**

Plugin models are now available in NetBox's Content Type framework (webhooks, scripts, etc.).

---

## [0.2.7] - 2026-02-26

### Fixed — **Cable creation via ORM**

`CableTermination` rows are now created correctly when a cable is created. Cable sync works end-to-end.

---

## [0.2.6] - 2026-02-26

### Changed — **Settings page redesign**

Grouped Bootstrap card sections with a user-friendly overview of all sync settings.

---

## [0.2.5] - 2026-02-26

### Changed — **JSON fields replaced with user-friendly inputs**

The three Settings fields that previously required raw JSON are now ordinary
text fields that everyone can use without knowing JSON syntax.

| Field | Old format | New format |
|---|---|---|
| **Default tags** | `["unifi", "wifi"]` | `unifi, wifi` (comma-separated text input) |
| **Asset tag patterns** | `["[-_]?(A?ID\\d+)$"]` | One regex per line (textarea) |
| **NetBox role mappings** | `{"WIRELESS": "Wireless AP", ...}` | `WIRELESS = Wireless AP` (one mapping per line) |

All three fields continue to store the same data in the database — only the
input widget has changed.  Existing saved values are converted automatically
when the Settings page is loaded.

Validation is unchanged: asset-tag patterns are still tested as regular
expressions, and role mappings still require at least one entry.

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/forms.py` | New `_CommaSeparatedField`, `_OnePerLineField`, `_KeyValueField`; replaced `JSONTextAreaField`; renamed form fields |

## [0.2.4] - 2026-02-26

### Fixed — **Complete and validated device status dropdown**

`netbox_device_status` now uses the full set of NetBox 4.x `DeviceStatusChoices`
slugs in the correct order, including the previously missing `failed` value.

`GlobalSyncSettings.clean()` now validates the stored value against the known
set and normalises it to lowercase before saving, so manually entered values
(e.g. via shell or PLUGINS_CONFIG) are also validated.

**Valid values:** `offline`, `active`, `planned`, `staged`, `failed`,
`inventory`, `decommissioning`

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/forms.py` | Added `failed`; reordered choices to match NetBox UI order |
| `netbox_unifi_sync/models.py` | Added `VALID_DEVICE_STATUSES` + validation in `clean()` |

## [0.2.3] - 2026-02-26

### Added — **Feature parity with standalone unifi2netbox**

Six settings that existed in the standalone CLI tool were missing from the
plugin UI and DB model.  They have now been added to `GlobalSyncSettings`
(migration `0005`) and are fully wired through the orchestrator and the
`plugin_settings_to_env` layer so the sync engine picks them up as env vars.

| New field | Env var | Default | Description |
|---|---|---|---|
| `dhcp_ranges` (TextField) | `DHCP_RANGES` | *(empty)* | Manual DHCP CIDR ranges, one per line.  Merged with auto-discovered ranges. |
| `sync_dhcp_ranges` (BooleanField) | `SYNC_DHCP_RANGES` | `true` | Toggle syncing DHCP IP ranges to NetBox IPAM. |
| `default_gateway` (GenericIPAddressField) | `DEFAULT_GATEWAY` | *(null)* | Fallback gateway for DHCP→static IP conversion when UniFi lacks gateway config. |
| `default_dns` (CharField, comma-separated) | `DEFAULT_DNS` | *(empty)* | Fallback DNS server(s) for DHCP→static conversion. |
| `netbox_device_status` (CharField) | `NETBOX_DEVICE_STATUS` | `planned` | Status assigned to newly created NetBox devices. |
| `sync_prefixes` (BooleanField) | `SYNC_PREFIXES` | `true` | Sync network prefixes from UniFi to NetBox IPAM. |

### Files changed

| File | Change |
|---|---|
| `netbox_unifi_sync/models.py` | Six new fields on `GlobalSyncSettings` |
| `netbox_unifi_sync/migrations/0005_feature_parity.py` | New migration |
| `netbox_unifi_sync/services/orchestrator.py` | `_build_override()` passes new fields |
| `netbox_unifi_sync/configuration.py` | New keys in `DEFAULT_SETTINGS` and `_ENV_MAP` |
| `netbox_unifi_sync/forms.py` | Widget overrides for `dhcp_ranges` and `netbox_device_status` |

### Migration

Run `python manage.py migrate netbox_unifi_sync` to apply migration `0005`
which adds the six new columns.  All columns have safe defaults so existing
rows are migrated automatically without data loss.

## [0.2.2] - 2026-02-26

### Fixed — **Device types and devices not created (ORM create regression)**

Two bugs in the Django ORM adapter (`netbox_orm.py`) introduced in v0.2.0
prevented all new Device Types and Devices from being created during sync.

#### Bug 1 — `full_clean()` rejected valid payloads

`_Endpoint.create()` called `instance.full_clean()` before `instance.save()`.
NetBox model validators (notably `_clean_custom_fields()`) run against the full
NetBox runtime context and raise `ValidationError` on unsaved instances even
when the payload is valid.  The NetBox REST API uses DRF serialiser validation,
not `model.full_clean()`, so the ORM adapter must match that behaviour.

**Fix:** Removed `full_clean()` call.  Django's `save()` enforces `NOT NULL` and
`UNIQUE` constraints at the database level.

#### Bug 2 — FK fields passed as integers caused descriptor errors

Payloads like `{'manufacturer': 5, 'model': 'UAP-AC-Pro', ...}` assigned an
integer directly to a `ForeignKey` field.  Under Django 5 (used by NetBox 4.x),
the FK descriptor can attempt to resolve the related instance during model
construction, which may raise `ValueError` or trigger an unexpected DB query.

**Fix:** `_Endpoint.create()` now introspects `model._meta` to find all
`ForeignKey` fields and rewrites `{'field': int}` → `{'field_id': int}` before
constructing the model instance.  This is the canonical Django ORM pattern.

#### Bug 3 — `get_postable_fields()` fallback was insufficient

If Django model introspection failed (e.g. during tests or early boot),
`get_postable_fields('', '', 'dcim/devices')` returned `{}`.  The device
creation code checked `if 'role' in available_fields` and silently skipped
every device with log message *"Could not determine the syntax for the role"*.

**Fix:** A guaranteed minimum field set is now always merged in after
introspection so callers never get a false negative:
```python
_GUARANTEED = {
    "dcim/devices": {"role": True, "status": True, "device_role": True},
}
```

### Files changed

| File | Change |
|---|---|
| `unifi2netbox/services/sync/netbox_orm.py` | Remove `full_clean()`; add `_fk_fields()` to rewrite FK ints to `_id` attnames |
| `unifi2netbox/services/sync_engine.py` | Add `_GUARANTEED` field set to `get_postable_fields()` |

## [0.2.1] - 2026-02-26

### Fixed — **NetBox plugin entry point added to wheel**

The package was missing the `[project.entry-points."netbox.plugins"]` declaration
in `pyproject.toml`.  Without it the built wheel contained no `entry_points.txt`,
so package-manager based plugin discovery (the mechanism NetBox uses to locate
plugins installed via `pip`) did not work.

**Required in every NetBox plugin:**
```toml
[project.entry-points."netbox.plugins"]
netbox_unifi_sync = "netbox_unifi_sync"
```

Manual installation via `PLUGINS = ["netbox_unifi_sync"]` in `configuration.py`
continued to work, but the entry point is required for full standard compliance.

### Verified — NetBox plugin standard checklist

| Check | Status |
|---|---|
| `PluginConfig` with `name`, `verbose_name`, `version`, `author`, `base_url` | ✅ |
| `min_version` / `max_version` (`4.2.0` – `4.99.99`) | ✅ |
| `config = NetBoxUnifiSyncConfig` in `__init__.py` | ✅ |
| `menu = "navigation.menu"` (relative dotted path) | ✅ |
| `PluginMenu` / `PluginMenuItem` / `PluginMenuButton` in `navigation.py` | ✅ |
| `app_name` set in `urls.py` | ✅ |
| `netbox.jobs.JobRunner` + `system_job` for scheduled tasks | ✅ |
| Migrations present and clean (0001–0004) | ✅ |
| `[project.entry-points."netbox.plugins"]` in `pyproject.toml` | ✅ (added this release) |

## [0.2.0] - 2026-02-26

### Changed — **Architecture: Django ORM replaces pynetbox HTTP self-calls**

The sync engine previously used `pynetbox` (an HTTP REST client) to read and
write NetBox data.  Because the plugin runs *inside* the NetBox/Django process
it can access the database directly via the Django ORM — no HTTP round-trip
is needed.

All NetBox reads and writes in `sync_engine.py`, `vrf.py`, and the surrounding
helper modules now go through a thin Django ORM adapter
(`unifi2netbox.services.sync.netbox_orm.build_netbox_orm_client()`).  The
adapter exposes the same `nb.dcim.devices.get(...)`, `.filter(...)`, `.all()`
and `.create(...)` surface that the sync engine already used, so no logic in
the sync engine needed to change.

### Removed

- **`netbox_url`** field removed from `GlobalSyncSettings` model (migration
  `0004` drops the column).  The field was added in 0.1.8 to let operators
  override the internal HTTP self-call URL — it is no longer needed.
- **`pynetbox~=7.4.1`** removed from package dependencies.
- `_resolve_internal_netbox_url()`, `_resolve_internal_netbox_token()`, and
  `_inject_internal_netbox_runtime_context()` removed from `sync_service.py`.
- `netbox_url`/`netbox_token` removed from `DEFAULT_SETTINGS` and `_ENV_MAP`
  in `configuration.py`; `netbox_token` removed from `_SECRET_FIELDS`.
- `get_postable_fields()` in `sync_engine.py` no longer makes HTTP OPTIONS
  requests — it now introspects Django model `_meta` to discover writable
  fields.

### Migration

Run `python manage.py migrate netbox_unifi_sync` to apply migration `0004`
which drops the `netbox_url` column.

If you have `netbox_url` set in your `PLUGINS_CONFIG`, remove it — it is no
longer used.

### Added
- Gateway and DNS are now read from UniFi network config (`gateway_ip`, `dhcpd_dns_1-4`) for DHCP-to-static IP conversion.
- Fallback env vars `DEFAULT_GATEWAY` and `DEFAULT_DNS` when UniFi network config lacks gateway/DNS.
- 20 new unit tests covering `_get_network_info_for_ip`, `extract_dhcp_ranges_from_unifi` network info, and `is_ip_in_dhcp_range`.
- TLS verification configuration flags:
  - `UNIFI_VERIFY_SSL` (default: `true`)
  - `NETBOX_VERIFY_SSL` (default: `true`)
- UniFi session cache control:
  - `UNIFI_PERSIST_SESSION` (default: `true`)
- Robust integer parsing helper for runtime env vars (used for sync interval and cleanup grace period).

### Changed
- Runtime startup validation logs now use `logger.error(...)` for fail-fast config checks (instead of `logger.exception(...)` outside `except` blocks).
- NetBox HTTP session verify behavior is now driven by `NETBOX_VERIFY_SSL`.
- UniFi request verify behavior is now driven by `UNIFI_VERIFY_SSL`.
- `README.md`, `docs/configuration.md`, `docs/architecture.md`, and `docs/troubleshooting.md` updated to match current TLS/session behavior.
- Docker image metadata source URL corrected to the active repository.

### Security
- UniFi session cache file writes now enforce restrictive permissions (`0600`).
- Integration API auth headers are no longer persisted to session cache on disk.

### Removed
- Raw auto-generated git-log changelog format replaced by structured release notes.

## [0.1.9] - 2026-02-26

### Fixed
- JSON API endpoints (`api/status/`, `api/controllers/<pk>/test/`) were defined but
  not reachable — `api/urls.py` was never included in the plugin's `urls.py`.
  Endpoints are now mounted at `/plugins/unifi-sync/api/` and return JSON responses.

### Changed
- `api/urls.py` `app_name` corrected from `"netbox_unifi_sync-api"` (dash breaks Django
  namespace resolution) to `"netbox_unifi_sync_api"`.

## [0.1.8] - 2026-02-26

### Fixed
- Sync worker no longer falls back to `http://localhost` when `ALLOWED_HOSTS` contains
  only `["*"]` or a hostname without a port. The internal NetBox URL is now resolved as
  `http://127.0.0.1:<port>` (port extracted from `ALLOWED_HOSTS` when present, defaulting
  to `8000`). Fixes `could not be found` errors on standard Debian/venv installs where
  gunicorn listens on port 8000.

### Added
- `netbox_url` field on `GlobalSyncSettings` (Settings UI). Set this to the internal API
  base URL (e.g. `http://127.0.0.1:8000`) to override auto-detection. Leave blank to
  auto-detect.

## [0.1.7] - 2026-02-26

### Fixed
- `verify_ssl` controller setting now propagates correctly through the dry-run preflight path (`auth.py` `build_client()`).
  Previously `UnifiAuthSettings` had no `verify_ssl` field, so dry-run connection tests always used `verify_ssl=True`
  regardless of the controller's setting, causing SSL failures on self-signed certificates during dry-run.

## [0.1.6] - 2026-02-26

### Fixed
- `verify_ssl` controller setting now takes effect during Integration API probe.
  Previously `verify_ssl=False` on the controller was ignored during `__init__`
  because `configure_integration_api()` ran before the setting was applied,
  causing SSL validation failures on self-signed certificates.

## [0.1.5] - 2026-02-26

### Fixed
- Documentation corrections: removed outdated `API_TOKEN_PEPPERS` snippet, fixed `netbox:8080` references, translated wiki to English.

## [0.1.4] - 2026-02-26

### Fixed
- NetBox URL resolution now works on all platforms (venv, Docker, LXC).
  The plugin derives the internal NetBox URL from Django `ALLOWED_HOSTS` and
  `SESSION_COOKIE_SECURE`, falling back to `http://localhost`. The hardcoded
  Docker-only fallback `http://netbox:8080` has been removed.

## [0.1.3] - 2026-02-26

### Changed
- Bumped release version to `0.1.3`.
- Clarified credential policy: UniFi API key/login credentials are configured in `Controllers` UI fields.
- Updated install/config docs and wiki for Debian server flow and plugin bootstrap usage.

### Fixed
- Improved controller credential guidance in UI help and runtime error messages.

## 2026-02-25

### Fixed
- Bumped release version to `0.1.2` to avoid PyPI filename reuse rejection after prior `0.1.0` artifact deletion and existing `v0.1.1` tag collision.

## 2026-02-16

### Changed
- Repository cleanup and documentation alignment with current implementation.
- CI workflow updated to install `pytest` explicitly while keeping runtime dependencies minimal.
- Dockerfile aligned with current runtime files.
- LXC scripts updated for current repository URL and simplified install flow.

### Removed
- Unused standalone files: `unifi_client.py`, `config.py`, `exceptions.py`, `utils.py`.
- Dead code and unused imports across core modules and tests.

## 2025-02-12

### Added
- Unit test suite and CI pipeline.
- Thread limits configurable via environment variables.

### Removed
- `README-old.md` (obsolete).

### Fixed
- `.gitignore` updated with key file ignores.

## 2025-02-11

### Added
- Community device specs bundle integration.
- Generic template sync for interface/console/power templates.
- NetBox cleanup workflow.
- Auto-create device types from discovered models.
- Continuous sync loop via `SYNC_INTERVAL`.

### Fixed
- Case-insensitive part number lookup behavior.

## 2025-02-10

### Added
- DHCP auto-discovery from UniFi network configuration.
- Merge of discovered DHCP ranges with manual `DHCP_RANGES`.
- `DHCP_AUTO_DISCOVER` toggle.

## 2025-02-09

### Added
- Built-in UniFi model specs and interface template sync.
- Device type enrichment (part number, U height, PoE budget).

### Changed
- Concurrency/race condition hardening for tagging paths.

## 2025-02-08

### Added
- Cable sync and stale/offline device handling.

### Improved
- Reliability improvements in concurrent controller processing.
