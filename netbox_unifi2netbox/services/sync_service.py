from __future__ import annotations

import logging
from typing import Any

import requests

from main import run_sync_once
from unifi.unifi import Unifi

from ..configuration import (
    get_plugin_settings,
    patched_environ,
    plugin_settings_to_env,
    resolve_secret_value,
    sanitize_plugin_settings,
    validate_plugin_settings,
)
from .mapping import format_result_summary

logger = logging.getLogger("netbox.plugins.netbox_unifi2netbox.sync")


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
    base_url = str(resolve_secret_value(plugin_settings.get("netbox_url") or "")).rstrip("/")
    token = str(resolve_secret_value(plugin_settings.get("netbox_token") or ""))
    verify_ssl = bool(plugin_settings.get("netbox_verify_ssl", True))
    timeout = int(plugin_settings.get("unifi_request_timeout", 15) or 15)

    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
    }
    response = requests.get(
        f"{base_url}/api/status/",
        headers=headers,
        timeout=timeout,
        verify=verify_ssl,
    )
    response.raise_for_status()
    payload = response.json() if response.content else {}
    return {
        "url": base_url,
        "status": "ok",
        "netbox_version": payload.get("netbox-version") or payload.get("version"),
    }


def _preflight_unifi(plugin_settings: dict[str, Any]) -> list[dict[str, Any]]:
    urls = _as_list(resolve_secret_value(plugin_settings.get("unifi_urls") or []))
    username = str(resolve_secret_value(plugin_settings.get("unifi_username") or ""))
    password = str(resolve_secret_value(plugin_settings.get("unifi_password") or ""))
    mfa_secret = str(resolve_secret_value(plugin_settings.get("unifi_mfa_secret") or ""))
    api_key = str(resolve_secret_value(plugin_settings.get("unifi_api_key") or ""))
    api_key_header = str(resolve_secret_value(plugin_settings.get("unifi_api_key_header") or ""))

    checks: list[dict[str, Any]] = []
    for raw_url in urls:
        url = str(raw_url).strip()
        if not url:
            continue

        try:
            controller = Unifi(
                base_url=url,
                username=username or None,
                password=password or None,
                mfa_secret=mfa_secret or None,
                api_key=api_key or None,
                api_key_header=api_key_header or None,
            )
            sites = getattr(controller, "sites", [])
            checks.append(
                {
                    "url": url,
                    "status": "ok",
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
) -> dict[str, Any]:
    """Execute one sync cycle or dry-run preflight using current plugin settings."""
    plugin_settings = get_plugin_settings(config_overrides)
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
