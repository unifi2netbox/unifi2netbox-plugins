# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

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
