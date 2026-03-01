# TODO — netbox-unifi-sync

**Current version:** `v0.3.17` (tagged, pushed to GitHub, CI publishes to PyPI)
**State:** ruff clean · bandit 0 issues (noisy nosec warnings, see P3) · 150 tests pass (1 skipped) · no uncommitted changes

---

## Done ✅

| Area | Detail |
|---|---|
| Security: `write_only` API fields | `password`, `token_value` not returned in GET — Proxmox2Netbox only (not applicable here, done on other repo). |
| Security: bandit B110 | All `except Exception: pass` blocks narrowed (ValueError/LookupError) or converted to `except Exception as exc: logger.debug(...)`. |
| Security: bandit B105 | `# nosec B105` on false-positive credential strings in `configuration.py`, `forms.py`, `models.py`. |
| Stability: bounds validation | `GlobalSyncSettings.clean()` enforces >= 1 for `request_timeout`, `max_controller_threads`, `max_site_threads`, `max_device_threads`. |
| Stability: stale pynetbox dep | Removed `pynetbox~=7.4.1` from `requirements.txt`. |
| Stability: mixed credentials | `_validate_runtime_config` no longer raises `SyncConfigurationError` — warns and disables cleanup, sync continues. |
| Lint: F401/F841 | All unused imports and variables cleaned. `_sync_interval_seconds`, `_netbox_verify_ssl` re-exported from `sync_engine` for test alias. |
| Tests: stale references | `extract_dhcp_ranges_from_unifi` → `extract_dhcp_pools_from_unifi` in `test_network_info.py`. |
| Tests: `_validation.py` | 7 unit tests for `validate_runtime_config` — all branches covered. |
| Refactor: `_validation.py` | `SyncConfigurationError` + `validate_runtime_config` extracted to pure module (no Django deps). |
| CVE scan | `pip-audit`: no known vulnerabilities in pinned deps. |

---

## In Progress 🔄

Nothing actively in progress. All changes committed and pushed.

---

## Next — Prioritised Backlog

### P1 — Clean up noisy `# nosec B105` in `configuration.py`

`bandit` emits ~50 `[tester] WARNING nosec encountered (B105), but no failed test` lines for `configuration.py:27–69` because `# nosec B105` was added to lines (33, 35, 36) that don't actually trigger B105 in the current bandit version. This is noisy in CI output but not a failure.

**Fix:** Remove `# nosec` from lines that don't trigger B105; keep only those that do. Run `python3 -m bandit netbox_unifi_sync/configuration.py` to find which specific lines actually fire, then annotate only those.

```bash
cd /opt/apps/netbox-unifi-sync
python3 -m bandit netbox_unifi_sync/configuration.py --format txt 2>&1 | grep "Location"
```

### P2 — Narrow remaining 74 `except Exception` in `sync_engine.py`

74 broad catches remain. Most are intentional guards in the legacy sync pipeline (pynetbox API calls that may throw unknown exception types). Approach:

- Audit each location: `grep -n "except Exception" netbox_unifi_sync/services/sync_engine.py`
- For pynetbox API call guards: wrap in `except Exception as exc: logger.warning(...)` (already partially done)
- For truly unknown/unavoidable types: add `# nosec B110` with a comment explaining why
- Target: reduce from 74 to <20 unnamed catches; ensure all remaining ones log at debug/warning level

### P3 — Integration test framework

`tests/integration/test_netbox_plugin_smoke.py` is a single skip placeholder. There is no mechanism to run integration tests against a real NetBox+UniFi environment.

**Approach:**
- Add `pytest-docker` or environment-variable gating (`INTEGRATION_TESTS=1`)
- Write smoke tests for:
  - `GlobalSyncSettings` singleton creation
  - `UnifiController` CRUD via Django ORM
  - `orchestrator.run_sync(dry_run=True, ...)` with a mocked UniFi client

### P4 — `sync_engine.py` decomposition

`sync_engine.py` is 3366 lines. It contains: device sync, interface sync, VLAN sync, WLAN sync, IPAM sync, cable sync, cleanup, DHCP parsing, and more.

**Goal:** Split into domain modules matching the existing `sync/` subdirectory pattern:
- `sync/devices.py` — device upsert, role assignment
- `sync/interfaces.py` — interface sync, cable sync
- `sync/wlans.py` — WLAN/SSID sync
- `sync/_engine.py` — orchestration of the above

**Risk:** High refactoring surface. Must be done incrementally, one domain at a time, with test coverage verified after each extraction. Not a priority until P2 (test coverage) improves.

### P5 — `configuration.py` deprecation path

`configuration.py` holds `DEFAULT_SETTINGS` — a legacy dict-based config used before the Django model (`GlobalSyncSettings`) was the primary source of truth. It still serves as fallback for `PLUGINS_CONFIG`-based deployments but is confusing alongside the DB model.

- Document which keys are still read from `PLUGINS_CONFIG` vs. DB-only
- Add a deprecation warning if any non-empty values are present in `PLUGINS_CONFIG`
- Long-term: remove in a future minor version once DB model covers all settings

### P6 — Scheduler robustness

`scheduler_due()` in `orchestrator.py` compares `last_auto_sync` against `now()`. If the RQ worker crashes mid-sync, `last_auto_sync` may never be updated, causing the scheduler to fire immediately on restart.

- Add `SchedulerState.sync_in_progress: BooleanField` or a lock timestamp
- Check and clear stale locks on worker startup

---

## Known Risks / Clarifications

| Risk | Detail |
|---|---|
| 74 broad `except Exception` in `sync_engine.py` | Majority are intentional guards around pynetbox/UniFi API calls that can throw unknown exception types. They are NOT security risks but reduce observability. All now log at debug level (as of v0.3.17). |
| `configuration.py` nosec noise | bandit warns about `# nosec B105` on lines that don't trigger B105. Exit code is 0 (no real issues), but CI output is noisy. Harmless. |
| Mixed credentials + cleanup | Cleanup is correctly skipped when controllers have different credentials. The underlying limitation (cleanup needs all serials from all controllers) is architectural and requires a major refactor to fully resolve. |
| `sync_engine.py` size | At 3366 lines, adding features or fixing bugs is high-risk due to lack of module boundaries. Any PR touching sync_engine should be small and targeted. |
| `GlobalSyncSettings` singleton | Enforced by `singleton_key="unique"` constraint. If the constraint is violated at the DB level (e.g. direct SQL insert), the plugin will malfunction. |
| `SchedulerState` last_auto_sync | Timestamp is only updated via `mark_scheduler_tick()`. If the scheduler fires but sync crashes before `mark_scheduler_tick()`, the scheduler will fire again immediately on the next tick. |

---

## How to Resume

```bash
cd /opt/apps/netbox-unifi-sync

# Verify baseline
python3 -m pytest tests/ -q                          # expect: 150 passed, 1 skipped
python3 -m ruff check netbox_unifi_sync/             # expect: All checks passed!
python3 -m bandit -r netbox_unifi_sync/ -ll          # expect: No issues identified

# Investigate nosec noise (P1):
python3 -m bandit netbox_unifi_sync/configuration.py --format txt 2>&1

# Audit broad except blocks (P2):
grep -n "except Exception" netbox_unifi_sync/services/sync_engine.py | wc -l
grep -n "except Exception" netbox_unifi_sync/services/sync_engine.py | head -30

# Release flow (after bumping version in pyproject.toml + netbox_unifi_sync/version.py):
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main && git push origin vX.Y.Z
```
