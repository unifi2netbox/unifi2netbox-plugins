from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

try:  # pragma: no cover - import-time compatibility shim
    from django.conf import settings as django_settings
    from django.core.exceptions import ImproperlyConfigured
except Exception:  # pragma: no cover
    django_settings = None

    class ImproperlyConfigured(Exception):
        pass


PLUGIN_NAME = "netbox_unifi2netbox"
_SECRET_FIELDS = {
    "unifi_api_key",
    "unifi_password",
    "netbox_token",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "unifi_urls": [],
    "unifi_api_key": "",
    "unifi_api_key_header": "X-API-KEY",
    "unifi_username": "",
    "unifi_password": "",
    "unifi_mfa_secret": "",
    "unifi_verify_ssl": True,
    "unifi_persist_session": True,
    "netbox_url": "",
    "netbox_token": "",
    "netbox_import_tenant": "",
    "netbox_tenant": "",
    "netbox_verify_ssl": True,
    "netbox_serial_mode": "mac",
    "netbox_vrf_mode": "existing",
    "netbox_default_vrf": "",
    "netbox_roles": {},
    "default_site_name": "",
    "unifi_use_site_mapping": False,
    "unifi_site_mappings": {},
    "tag_strategy": "append",
    "default_tags": [],
    "sync_interfaces": True,
    "sync_vlans": True,
    "sync_wlans": True,
    "sync_cables": True,
    "sync_stale_cleanup": True,
    "netbox_cleanup": False,
    "cleanup_stale_days": 30,
    "dry_run_default": False,
    "dhcp_auto_discover": True,
    "dhcp_ranges": [],
    "default_gateway": "",
    "default_dns": [],
    "max_controller_threads": 5,
    "max_site_threads": 8,
    "max_device_threads": 8,
    "rate_limit_per_second": 0,
    "unifi_request_timeout": 15,
    "unifi_http_retries": 3,
    "unifi_retry_backoff_base": 1.0,
    "unifi_retry_backoff_max": 30.0,
    "unifi_specs_auto_refresh": False,
    "unifi_specs_include_store": False,
    "unifi_specs_refresh_timeout": 45,
    "unifi_specs_store_timeout": 15,
    "unifi_specs_store_max_workers": 8,
    "unifi_specs_write_cache": False,
    "sync_interval_minutes": 0,
    "extra_env": {},
}

_ENV_MAP: dict[str, str] = {
    "unifi_api_key": "UNIFI_API_KEY",
    "unifi_api_key_header": "UNIFI_API_KEY_HEADER",
    "unifi_username": "UNIFI_USERNAME",
    "unifi_password": "UNIFI_PASSWORD",
    "unifi_mfa_secret": "UNIFI_MFA_SECRET",
    "unifi_verify_ssl": "UNIFI_VERIFY_SSL",
    "unifi_persist_session": "UNIFI_PERSIST_SESSION",
    "netbox_url": "NETBOX_URL",
    "netbox_token": "NETBOX_TOKEN",
    "netbox_verify_ssl": "NETBOX_VERIFY_SSL",
    "netbox_serial_mode": "NETBOX_SERIAL_MODE",
    "netbox_vrf_mode": "NETBOX_VRF_MODE",
    "netbox_default_vrf": "NETBOX_DEFAULT_VRF",
    "unifi_use_site_mapping": "UNIFI_USE_SITE_MAPPING",
    "sync_interfaces": "SYNC_INTERFACES",
    "sync_vlans": "SYNC_VLANS",
    "sync_wlans": "SYNC_WLANS",
    "sync_cables": "SYNC_CABLES",
    "sync_stale_cleanup": "SYNC_STALE_CLEANUP",
    "netbox_cleanup": "NETBOX_CLEANUP",
    "cleanup_stale_days": "CLEANUP_STALE_DAYS",
    "dhcp_auto_discover": "DHCP_AUTO_DISCOVER",
    "default_gateway": "DEFAULT_GATEWAY",
    "max_controller_threads": "MAX_CONTROLLER_THREADS",
    "max_site_threads": "MAX_SITE_THREADS",
    "max_device_threads": "MAX_DEVICE_THREADS",
    "unifi_request_timeout": "UNIFI_REQUEST_TIMEOUT",
    "unifi_http_retries": "UNIFI_HTTP_RETRIES",
    "unifi_retry_backoff_base": "UNIFI_RETRY_BACKOFF_BASE",
    "unifi_retry_backoff_max": "UNIFI_RETRY_BACKOFF_MAX",
    "unifi_specs_auto_refresh": "UNIFI_SPECS_AUTO_REFRESH",
    "unifi_specs_include_store": "UNIFI_SPECS_INCLUDE_STORE",
    "unifi_specs_refresh_timeout": "UNIFI_SPECS_REFRESH_TIMEOUT",
    "unifi_specs_store_timeout": "UNIFI_SPECS_STORE_TIMEOUT",
    "unifi_specs_store_max_workers": "UNIFI_SPECS_STORE_MAX_WORKERS",
    "unifi_specs_write_cache": "UNIFI_SPECS_WRITE_CACHE",
    "tag_strategy": "UNIFI_TAG_STRATEGY",
    "default_site_name": "NETBOX_DEFAULT_SITE",
    "rate_limit_per_second": "UNIFI_RATE_LIMIT_PER_SECOND",
}


def _plugins_config() -> dict[str, Any]:
    if django_settings is None:
        return {}
    try:
        loaded = getattr(django_settings, "PLUGINS_CONFIG", {})
    except ImproperlyConfigured:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def resolve_secret_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if text.startswith("env:"):
        env_name = text[4:].strip()
        return os.getenv(env_name, "") if env_name else ""
    if text.startswith("file:"):
        file_path = text[5:].strip()
        if not file_path:
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return ""
    return value


def _as_bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip().startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _as_mapping(value: Any) -> dict[str, str]:
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    if isinstance(value, dict):
        return {
            str(key).strip(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and str(item).strip()
        }
    return {}


def get_plugin_settings(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    configured = _plugins_config().get(PLUGIN_NAME, {})
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(configured, dict):
        merged.update(configured)
    if isinstance(overrides, dict):
        merged.update(overrides)
    return merged


def sanitize_plugin_settings(plugin_settings: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    for key, value in plugin_settings.items():
        if key in _SECRET_FIELDS:
            resolved = resolve_secret_value(value)
            sanitized[key] = "***" if str(resolved).strip() else ""
        elif key == "extra_env" and isinstance(value, dict):
            sanitized[key] = {
                env_name: ("***" if any(part in str(env_name).upper() for part in ("TOKEN", "SECRET", "KEY", "PASS")) else env_value)
                for env_name, env_value in value.items()
            }
        else:
            sanitized[key] = value
    return sanitized


def plugin_settings_to_env(plugin_settings: dict[str, Any]) -> dict[str, str]:
    env_values: dict[str, str] = {}

    urls = _as_list(resolve_secret_value(plugin_settings.get("unifi_urls")))
    if urls:
        env_values["UNIFI_URLS"] = json.dumps(urls)

    site_mappings = _as_mapping(resolve_secret_value(plugin_settings.get("unifi_site_mappings")))
    if site_mappings:
        env_values["UNIFI_SITE_MAPPINGS"] = json.dumps(site_mappings)

    roles = _as_mapping(resolve_secret_value(plugin_settings.get("netbox_roles")))
    if roles:
        env_values["NETBOX_ROLES"] = json.dumps({key.upper(): value for key, value in roles.items()})

    default_tags = _as_list(resolve_secret_value(plugin_settings.get("default_tags")))
    if default_tags:
        env_values["UNIFI_DEFAULT_TAGS"] = ",".join(default_tags)

    dhcp_ranges = _as_list(resolve_secret_value(plugin_settings.get("dhcp_ranges")))
    if dhcp_ranges:
        env_values["DHCP_RANGES"] = ",".join(dhcp_ranges)

    default_dns = _as_list(resolve_secret_value(plugin_settings.get("default_dns")))
    if default_dns:
        env_values["DEFAULT_DNS"] = ",".join(default_dns)

    tenant_import = str(resolve_secret_value(plugin_settings.get("netbox_import_tenant") or "")).strip()
    tenant_fallback = str(resolve_secret_value(plugin_settings.get("netbox_tenant") or "")).strip()
    if tenant_import:
        env_values["NETBOX_IMPORT_TENANT"] = tenant_import
    if tenant_fallback:
        env_values["NETBOX_TENANT"] = tenant_fallback

    for key, env_name in _ENV_MAP.items():
        value = resolve_secret_value(plugin_settings.get(key))
        if value is None:
            continue
        if isinstance(value, bool):
            env_values[env_name] = _as_bool_text(value)
            continue
        text = str(value).strip()
        if text:
            env_values[env_name] = text

    # Jobs always execute single-cycle runs; scheduling belongs to NetBox job scheduler.
    env_values["SYNC_INTERVAL"] = "0"

    extra_env = plugin_settings.get("extra_env")
    if isinstance(extra_env, dict):
        for env_name, raw_value in extra_env.items():
            key = str(env_name).strip()
            if not key:
                continue
            value = resolve_secret_value(raw_value)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                env_values[key] = text

    return env_values


def validate_plugin_settings(plugin_settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    urls = _as_list(resolve_secret_value(plugin_settings.get("unifi_urls")))
    if not urls:
        errors.append("Missing plugin setting 'unifi_urls'.")

    api_key = str(resolve_secret_value(plugin_settings.get("unifi_api_key") or "")).strip()
    username = str(resolve_secret_value(plugin_settings.get("unifi_username") or "")).strip()
    password = str(resolve_secret_value(plugin_settings.get("unifi_password") or "")).strip()
    if not api_key and not (username and password):
        errors.append("Configure either 'unifi_api_key' or both 'unifi_username' and 'unifi_password'.")

    if not str(resolve_secret_value(plugin_settings.get("netbox_url") or "")).strip():
        errors.append("Missing plugin setting 'netbox_url'.")

    if not str(resolve_secret_value(plugin_settings.get("netbox_token") or "")).strip():
        errors.append("Missing plugin setting 'netbox_token'.")

    tenant_import = str(resolve_secret_value(plugin_settings.get("netbox_import_tenant") or "")).strip()
    tenant_fallback = str(resolve_secret_value(plugin_settings.get("netbox_tenant") or "")).strip()
    if not (tenant_import or tenant_fallback):
        errors.append("Missing plugin setting 'netbox_import_tenant' (or 'netbox_tenant').")

    roles = _as_mapping(resolve_secret_value(plugin_settings.get("netbox_roles")))
    if not roles:
        errors.append("Missing plugin setting 'netbox_roles'.")

    tag_strategy = str(plugin_settings.get("tag_strategy") or "append").strip().lower()
    if tag_strategy not in {"append", "replace", "none"}:
        errors.append("'tag_strategy' must be one of: append, replace, none.")

    return errors


def get_sync_interval_minutes(plugin_settings: dict[str, Any] | None = None) -> int:
    settings_data = plugin_settings or get_plugin_settings()
    raw_value = settings_data.get("sync_interval_minutes", 0)
    try:
        interval = int(raw_value)
    except (TypeError, ValueError):
        return 0
    return max(0, interval)


@contextmanager
def patched_environ(values: dict[str, str]):
    original: dict[str, str | None] = {}
    for key, value in values.items():
        original[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, old_value in original.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
