from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Iterable

from django.utils import timezone
from netbox_unifi_sync.services.sync_service import execute_sync as legacy_execute_sync
from unifi2netbox.services.unifi.unifi import Unifi

from ..models import (
    AuthMode,
    GlobalSyncSettings,
    SchedulerState,
    SiteMapping,
    UnifiController,
)
from .audit import sanitize_error
from .runtime import auth_signature, redact_runtime, to_controller_runtime

logger = logging.getLogger("netbox.plugins.netbox_unifi_sync.orchestrator")

DEFAULT_ROLES = {
    "WIRELESS": "Wireless AP",
    "ROUTER": "Router",
    "SWITCH": "Switch",
    "SECURITY": "Security Appliance",
    "PHONE": "VoIP Phone",
    "OTHER": "Network Device",
}


class SyncConfigurationError(ValueError):
    pass


def get_or_create_global_settings() -> GlobalSyncSettings:
    obj, _ = GlobalSyncSettings.objects.get_or_create(
        singleton_key="default",
        defaults={
            "tenant_name": "Default",
            "netbox_roles": dict(DEFAULT_ROLES),
            "asset_tag_patterns": [r"[-_]?(A?ID\d+)$"],
        },
    )
    if not obj.netbox_roles:
        obj.netbox_roles = dict(DEFAULT_ROLES)
        obj.save(update_fields=["netbox_roles", "updated"])
    return obj


def get_enabled_controllers(controller_ids: Iterable[int] | None = None):
    queryset = UnifiController.objects.filter(enabled=True).order_by("name")
    if controller_ids:
        queryset = queryset.filter(pk__in=list(controller_ids))
    return list(queryset)


def _collect_site_mappings(controllers: list[UnifiController]) -> dict[str, str]:
    controller_ids = [item.pk for item in controllers if item.pk]
    mapping: dict[str, str] = {}

    global_rows = SiteMapping.objects.filter(enabled=True, controller__isnull=True)
    for row in global_rows:
        mapping[row.unifi_site] = row.netbox_site

    scoped_rows = SiteMapping.objects.filter(enabled=True, controller_id__in=controller_ids)
    for row in scoped_rows:
        mapping[row.unifi_site] = row.netbox_site

    return mapping


def _validate_runtime_config(settings: GlobalSyncSettings, runtime_groups: dict[tuple[str, ...], list[dict[str, Any]]], cleanup_requested: bool):
    if not settings.tenant_name.strip():
        raise SyncConfigurationError("tenant_name must be configured.")
    if not settings.netbox_roles:
        raise SyncConfigurationError("netbox_roles must be configured.")

    if cleanup_requested and len(runtime_groups) > 1:
        raise SyncConfigurationError(
            "Cleanup cannot run with mixed controller credentials. "
            "Use common credentials for all enabled controllers or disable cleanup for this run."
        )


def _build_override(
    settings: GlobalSyncSettings,
    runtime_rows: list[dict[str, Any]],
    site_mappings: dict[str, str],
    *,
    cleanup_enabled: bool,
) -> dict[str, Any]:
    first = runtime_rows[0]["runtime"]

    role_map = {str(k).upper(): str(v) for k, v in settings.netbox_roles.items() if str(k).strip() and str(v).strip()}
    if not role_map:
        role_map = dict(DEFAULT_ROLES)

    return {
        "unifi_urls": [row["runtime"].base_url for row in runtime_rows],
        "auth_mode": first.auth_mode,
        "api_key": first.api_key,
        "unifi_api_key_header": first.api_key_header,
        "username": first.username,
        "password": first.password,
        "unifi_mfa_secret": first.mfa_secret,
        "verify_ssl": bool(first.verify_ssl),
        "unifi_request_timeout": int(first.request_timeout),
        "unifi_http_retries": int(first.http_retries),
        "unifi_retry_backoff_base": float(first.retry_backoff_base),
        "unifi_retry_backoff_max": float(first.retry_backoff_max),

        "netbox_import_tenant": settings.tenant_name,
        "netbox_default_vrf": settings.default_vrf_name,
        "netbox_vrf_mode": settings.vrf_mode,
        "netbox_serial_mode": settings.serial_mode,
        "default_site": settings.default_site,
        "netbox_roles": role_map,

        "unifi_site_mappings": site_mappings,
        "tag_strategy": settings.tag_strategy,
        "default_tags": settings.default_tags,
        "asset_tag_enabled": settings.asset_tag_enabled,
        "asset_tag_patterns": settings.asset_tag_patterns or [r"[-_]?(A?ID\d+)$"],
        "asset_tag_uppercase": settings.asset_tag_uppercase,

        "sync_interfaces": settings.sync_interfaces,
        "sync_vlans": settings.sync_vlans,
        "sync_wlans": settings.sync_wlans,
        "sync_cables": settings.sync_cables,
        "sync_stale_cleanup": settings.sync_stale_cleanup,
        "netbox_cleanup": cleanup_enabled,
        "cleanup_stale_days": settings.cleanup_grace_days,

        "dhcp_auto_discover": settings.dhcp_auto_discover,
        "dhcp_writeback_enabled": settings.dhcp_writeback_enabled,

        "max_controller_threads": settings.max_controller_threads,
        "max_site_threads": settings.max_site_threads,
        "max_device_threads": settings.max_device_threads,
        "rate_limit_per_second": settings.rate_limit_per_second,

        "unifi_specs_auto_refresh": settings.specs_auto_refresh,
        "unifi_specs_include_store": settings.specs_include_store,
        "unifi_specs_refresh_timeout": settings.specs_refresh_timeout,
        "unifi_specs_store_timeout": settings.specs_store_timeout,
        "unifi_specs_store_max_workers": settings.specs_store_max_workers,
        "unifi_specs_write_cache": settings.specs_write_cache,
    }


def _build_unifi_client(runtime):
    if runtime.auth_mode == AuthMode.API_KEY:
        return Unifi(
            base_url=runtime.base_url,
            api_key=runtime.api_key,
            api_key_header=runtime.api_key_header,
            allow_login_fallback=False,
            verify_ssl=runtime.verify_ssl,
        )

    return Unifi(
        base_url=runtime.base_url,
        username=runtime.username,
        password=runtime.password,
        mfa_secret=runtime.mfa_secret or None,
        verify_ssl=runtime.verify_ssl,
    )


def _runtime_defaults(settings: GlobalSyncSettings) -> dict[str, Any]:
    return {
        "verify_ssl_default": settings.verify_ssl_default,
        "request_timeout": settings.request_timeout,
        "http_retries": settings.http_retries,
        "retry_backoff_base": settings.retry_backoff_base,
        "retry_backoff_max": settings.retry_backoff_max,
    }


def discover_unifi_site_names(settings: GlobalSyncSettings | None = None) -> list[str]:
    settings_obj = settings or get_or_create_global_settings()
    defaults = _runtime_defaults(settings_obj)
    names: set[str] = set()

    for controller in get_enabled_controllers():
        runtime = to_controller_runtime(controller, defaults)
        if runtime.auth_mode == AuthMode.API_KEY and not runtime.api_key:
            continue
        if runtime.auth_mode == AuthMode.LOGIN and (not runtime.username or not runtime.password):
            continue

        try:
            client = _build_unifi_client(runtime)
            client.verify_ssl = runtime.verify_ssl
            for site_name in getattr(client, "sites", {}).keys():
                site_name = str(site_name or "").strip()
                if site_name:
                    names.add(site_name)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            logger.warning(
                "Failed to fetch UniFi sites for controller '%s': %s",
                controller.name,
                sanitize_error(str(exc)),
            )

    return sorted(names, key=str.casefold)


def test_controller_connection(controller: UnifiController, settings: GlobalSyncSettings) -> dict[str, Any]:
    runtime = to_controller_runtime(
        controller,
        _runtime_defaults(settings),
    )

    if runtime.auth_mode == AuthMode.API_KEY and not runtime.api_key:
        raise SyncConfigurationError(
            f"Controller {controller.name}: missing API key credential "
            f"(set api_key_ref in Controllers UI)."
        )
    if runtime.auth_mode == AuthMode.LOGIN and (not runtime.username or not runtime.password):
        raise SyncConfigurationError(
            f"Controller {controller.name}: missing login credentials "
            f"(set username_ref/password_ref in Controllers UI)."
        )

    client = _build_unifi_client(runtime)
    client.verify_ssl = runtime.verify_ssl

    sites = getattr(client, "sites", [])
    return {
        "status": "ok",
        "controller": controller.name,
        "base_url": runtime.base_url,
        "auth_mode": runtime.auth_mode,
        "sites": len(sites),
        "runtime": redact_runtime(runtime),
    }


def run_sync(*, dry_run: bool, cleanup_requested: bool, requested_by_id: int | None = None, controller_ids: Iterable[int] | None = None) -> dict[str, Any]:
    settings = get_or_create_global_settings()
    if not settings.enabled:
        return {
            "mode": "dry-run" if dry_run else "sync",
            "controllers": 0,
            "sites": 0,
            "devices": 0,
            "details": {"status": "skipped", "reason": "Plugin settings disabled"},
        }

    controllers = get_enabled_controllers(controller_ids=controller_ids)
    if not controllers:
        raise SyncConfigurationError("No enabled UniFi controllers configured.")

    defaults = _runtime_defaults(settings)

    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for controller in controllers:
        runtime = to_controller_runtime(controller, defaults)
        sig = auth_signature(runtime)
        grouped[sig].append({"controller": controller, "runtime": runtime})

    _validate_runtime_config(settings, grouped, cleanup_requested)

    aggregate = {
        "mode": "dry-run" if dry_run else "sync",
        "controllers": 0,
        "sites": 0,
        "devices": 0,
        "details": {
            "groups": [],
            "cleanup_requested": cleanup_requested,
        },
    }

    for idx, rows in enumerate(grouped.values(), start=1):
        site_mappings = _collect_site_mappings([row["controller"] for row in rows])
        overrides = _build_override(
            settings,
            rows,
            site_mappings,
            cleanup_enabled=bool(cleanup_requested),
        )

        result = legacy_execute_sync(
            dry_run=dry_run,
            config_overrides=overrides,
            requested_by_id=requested_by_id,
        )
        aggregate["controllers"] += int(result.get("controllers", 0) or 0)
        aggregate["sites"] += int(result.get("sites", 0) or 0)
        aggregate["devices"] += int(result.get("devices", 0) or 0)
        aggregate["details"]["groups"].append(
            {
                "group": idx,
                "controllers": [row["controller"].name for row in rows],
                "result": result,
            }
        )

    return aggregate


def scheduler_due(settings: GlobalSyncSettings) -> bool:
    if not settings.enabled or not settings.schedule_enabled:
        return False

    state, _ = SchedulerState.objects.get_or_create(key="default")
    now = timezone.now()
    if not state.last_auto_sync:
        return True

    delta = now - state.last_auto_sync
    return delta.total_seconds() >= max(60, int(settings.sync_interval_minutes) * 60)


def mark_scheduler_tick():
    state, _ = SchedulerState.objects.get_or_create(key="default")
    state.last_auto_sync = timezone.now()
    state.save(update_fields=["last_auto_sync", "updated"])
