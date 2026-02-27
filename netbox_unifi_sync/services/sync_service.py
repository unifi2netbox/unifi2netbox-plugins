from __future__ import annotations

import logging
from typing import Any

from netbox_unifi_sync.services.sync_engine import run_sync_once

from ..configuration import (
    get_plugin_settings,
    normalize_plugin_settings,
    patched_environ,
    plugin_settings_to_env,
    resolve_secret_value,
    sanitize_plugin_settings,
    validate_plugin_settings,
)
from .auth import UnifiAuthSettings
from .mapping import format_result_summary

logger = logging.getLogger("netbox.plugins.netbox_unifi_sync.sync")


class SyncConfigurationError(ValueError):
    """Raised when plugin configuration is incomplete or invalid."""


def build_config_snapshot(plugin_settings: dict[str, Any]) -> dict[str, Any]:
    """Return plugin settings safe for persistence in run history."""
    return sanitize_plugin_settings(plugin_settings)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _preflight_netbox(plugin_settings: dict[str, Any]) -> dict[str, Any]:
    """
    Verify that the NetBox ORM layer is accessible.

    The plugin runs inside the Django/NetBox process, so there is no
    HTTP URL to resolve — we simply confirm that NetBox models can be
    imported and queried.
    """
    try:
        import netbox
        netbox_version = getattr(netbox, "VERSION", None)
    except Exception:
        netbox_version = None

    try:
        from dcim.models import Site  # noqa: F401 — import-only connectivity check
        orm_ok = True
    except Exception:
        orm_ok = False

    return {
        "url": "internal (ORM)",
        "status": "ok" if orm_ok else "error",
        "netbox_version": netbox_version,
    }


def _preflight_unifi(plugin_settings: dict[str, Any]) -> list[dict[str, Any]]:
    urls = _as_list(resolve_secret_value(plugin_settings.get("unifi_urls") or []))
    auth = UnifiAuthSettings.from_plugin_settings(plugin_settings)
    auth.validate()

    checks: list[dict[str, Any]] = []
    for raw_url in urls:
        url = str(raw_url).strip()
        if not url:
            continue

        try:
            controller = auth.build_client(base_url=url)
            sites = getattr(controller, "sites", [])
            checks.append(
                {
                    "url": url,
                    "status": "ok",
                    "auth_mode": auth.auth_mode,
                    "api_style": getattr(controller, "api_style", "unknown"),
                    "sites": len(sites),
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "url": url,
                    "status": "error",
                    "error": str(exc),
                }
            )

    return checks


def _run_preflight(plugin_settings: dict[str, Any]) -> dict[str, Any]:
    netbox_check = _preflight_netbox(plugin_settings)
    unifi_checks = _preflight_unifi(plugin_settings)
    failures = [item for item in unifi_checks if item.get("status") != "ok"]
    if failures:
        raise RuntimeError(f"UniFi preflight failed for {len(failures)} controller(s): {failures}")

    return {
        "mode": "dry-run",
        "netbox": netbox_check,
        "unifi_controllers": unifi_checks,
        "controllers": len(unifi_checks),
        "sites": sum(int(item.get("sites", 0)) for item in unifi_checks),
        "devices": 0,
    }


def execute_sync(
    *,
    dry_run: bool = False,
    config_overrides: dict[str, Any] | None = None,
    requested_by_id: int | None = None,
) -> dict[str, Any]:
    """Execute one sync cycle or dry-run preflight using current plugin settings."""
    if isinstance(config_overrides, dict):
        # In plugin runtime, UI/DB settings are passed as overrides.
        # Do not merge PLUGINS_CONFIG here; keep runtime source-of-truth in DB.
        plugin_settings = normalize_plugin_settings(config_overrides, include_defaults=True)
    else:
        plugin_settings = get_plugin_settings()

    validation_errors = validate_plugin_settings(plugin_settings)
    if validation_errors:
        raise SyncConfigurationError(" ".join(validation_errors))

    env_values = plugin_settings_to_env(plugin_settings)
    with patched_environ(env_values):
        if dry_run:
            result = _run_preflight(plugin_settings)
            logger.info("Dry-run preflight completed")
            return format_result_summary(result, dry_run=True)

        raw_result = run_sync_once(clear_state=True)
        logger.info("Sync run completed")
        return format_result_summary(raw_result, dry_run=False)


def format_sync_summary(result: dict[str, Any]) -> str:
    mode = result.get("mode", "sync")
    controllers = int(result.get("controllers", 0) or 0)
    sites = int(result.get("sites", 0) or 0)
    devices = int(result.get("devices", 0) or 0)
    return f"mode={mode} controllers={controllers} sites={sites} devices={devices}"
