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


PRIMARY_PLUGIN_NAME = "netbox_unifi_sync"
_SECRET_FIELDS = {
    "api_key",
    "password",
    "unifi_api_key",
    "unifi_password",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "auth_mode": "api_key",
    "unifi_url": "",
    "unifi_urls": [],
    "api_key": "",
    "unifi_api_key": "",
    "unifi_api_key_header": "X-API-KEY",
    "username": "",
    "unifi_username": "",
    "password": "",
    "unifi_password": "",
    "unifi_mfa_secret": "",
    "verify_ssl": True,
    "unifi_verify_ssl": True,
    "unifi_persist_session": True,
    "netbox_import_tenant": "",
    "netbox_tenant": "",
    "netbox_verify_ssl": True,
    "netbox_serial_mode": "mac",
    "netbox_vrf_mode": "existing",
    "netbox_default_vrf": "",
    "netbox_roles": {},
    "default_site": "",
    "default_site_name": "",
    "unifi_use_site_mapping": False,
    "unifi_site_mappings": {},
    "tag_strategy": "append",
    "default_tags": [],
    "asset_tag_enabled": True,
    "asset_tag_patterns": [],
    "asset_tag_uppercase": True,
    "sync_interfaces": True,
    "sync_vlans": True,
    "sync_wlans": True,
    "sync_cables": True,
    "sync_stale_cleanup": True,
    "netbox_cleanup": False,
    "cleanup_stale_days": 30,
    "dry_run": False,
    "dry_run_default": False,
    "dhcp_auto_discover": True,
    "dhcp_ranges": [],
    "sync_dhcp_ranges": True,
    "default_gateway": "",
    "default_dns": [],
    "netbox_device_status": "planned",
    "sync_prefixes": True,
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
    "unifi_verify_ssl": "UNIFI_VERIFY_SSL",
    "unifi_persist_session": "UNIFI_PERSIST_SESSION",
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
    "sync_dhcp_ranges": "SYNC_DHCP_RANGES",
    "default_gateway": "DEFAULT_GATEWAY",
    "netbox_device_status": "NETBOX_DEVICE_STATUS",
    "sync_prefixes": "SYNC_PREFIXES",
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
    "asset_tag_enabled": "UNIFI_ASSET_TAG_ENABLED",
    "asset_tag_uppercase": "UNIFI_ASSET_TAG_UPPERCASE",
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


def _as_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


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


def _normalize_auth_mode(raw_mode: Any, *, api_key: str, username: str, password: str) -> str:
    mode = str(raw_mode or "").strip().lower()
    if mode:
        return mode
    if api_key:
        return "api_key"
    if username and password:
        return "login"
    return "api_key"


def _normalize_plugin_settings(settings: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(settings)

    unifi_urls = _as_list(resolve_secret_value(normalized.get("unifi_urls")))
    if not unifi_urls:
        unifi_urls = _as_list(resolve_secret_value(normalized.get("unifi_url")))
    normalized["unifi_urls"] = unifi_urls
    normalized["unifi_url"] = unifi_urls[0] if unifi_urls else ""

    api_key = str(
        resolve_secret_value(
            normalized.get("unifi_api_key")
            or normalized.get("api_key")
            or ""
        )
    ).strip()
    username = str(
        resolve_secret_value(
            normalized.get("unifi_username")
            or normalized.get("username")
            or ""
        )
    ).strip()
    password = str(
        resolve_secret_value(
            normalized.get("unifi_password")
            or normalized.get("password")
            or ""
        )
    ).strip()

    normalized["unifi_api_key"] = api_key
    normalized["api_key"] = api_key
    normalized["unifi_username"] = username
    normalized["username"] = username
    normalized["unifi_password"] = password
    normalized["password"] = password

    if "verify_ssl" in settings:
        verify_ssl_source = settings.get("verify_ssl")
    else:
        verify_ssl_source = settings.get("unifi_verify_ssl", True)
    verify_ssl = _as_bool(verify_ssl_source, default=True)
    normalized["unifi_verify_ssl"] = verify_ssl
    normalized["verify_ssl"] = verify_ssl

    if "default_site" in settings:
        default_site_source = settings.get("default_site")
    else:
        default_site_source = settings.get("default_site_name")
    default_site = str(resolve_secret_value(default_site_source or "")).strip()
    normalized["default_site_name"] = default_site
    normalized["default_site"] = default_site

    if "dry_run" in settings:
        dry_run_source = settings.get("dry_run")
    else:
        dry_run_source = settings.get("dry_run_default", False)
    dry_run_default = _as_bool(dry_run_source, default=False)
    normalized["dry_run_default"] = dry_run_default
    normalized["dry_run"] = dry_run_default

    normalized["auth_mode"] = _normalize_auth_mode(
        normalized.get("auth_mode"),
        api_key=api_key,
        username=username,
        password=password,
    )
    return normalized


def normalize_plugin_settings(
    settings: dict[str, Any] | None = None,
    *,
    include_defaults: bool = False,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(DEFAULT_SETTINGS) if include_defaults else {}
    if isinstance(settings, dict):
        merged.update(settings)
    return _normalize_plugin_settings(merged)


def get_plugin_settings(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    loaded_plugins = _plugins_config()
    primary = loaded_plugins.get(PRIMARY_PLUGIN_NAME, {})
    if isinstance(primary, dict):
        merged.update(primary)
    if isinstance(overrides, dict):
        merged.update(overrides)
    return normalize_plugin_settings(merged)


def sanitize_plugin_settings(plugin_settings: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_plugin_settings(plugin_settings)
    sanitized = {}
    for key, value in normalized.items():
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
    plugin_settings = normalize_plugin_settings(plugin_settings)
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

    asset_tag_patterns = _as_list(resolve_secret_value(plugin_settings.get("asset_tag_patterns")))
    if asset_tag_patterns:
        env_values["UNIFI_ASSET_TAG_PATTERNS"] = json.dumps(asset_tag_patterns)

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

    auth_mode = str(plugin_settings.get("auth_mode") or "api_key").strip().lower()
    env_values["UNIFI_AUTH_MODE"] = auth_mode

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

    if auth_mode == "api_key":
        api_key = str(resolve_secret_value(plugin_settings.get("unifi_api_key") or "")).strip()
        if api_key:
            env_values["UNIFI_API_KEY"] = api_key
        api_key_header = str(resolve_secret_value(plugin_settings.get("unifi_api_key_header") or "")).strip()
        if api_key_header:
            env_values["UNIFI_API_KEY_HEADER"] = api_key_header
    elif auth_mode == "login":
        username = str(resolve_secret_value(plugin_settings.get("unifi_username") or "")).strip()
        password = str(resolve_secret_value(plugin_settings.get("unifi_password") or "")).strip()
        mfa_secret = str(resolve_secret_value(plugin_settings.get("unifi_mfa_secret") or "")).strip()
        if username:
            env_values["UNIFI_USERNAME"] = username
        if password:
            env_values["UNIFI_PASSWORD"] = password
        if mfa_secret:
            env_values["UNIFI_MFA_SECRET"] = mfa_secret

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
    plugin_settings = normalize_plugin_settings(plugin_settings)
    errors: list[str] = []

    urls = _as_list(resolve_secret_value(plugin_settings.get("unifi_urls")))
    if not urls:
        errors.append("Missing plugin setting 'unifi_url' (or 'unifi_urls').")

    auth_mode = str(plugin_settings.get("auth_mode") or "").strip().lower()
    api_key = str(resolve_secret_value(plugin_settings.get("unifi_api_key") or "")).strip()
    username = str(resolve_secret_value(plugin_settings.get("unifi_username") or "")).strip()
    password = str(resolve_secret_value(plugin_settings.get("unifi_password") or "")).strip()
    if auth_mode not in {"api_key", "login"}:
        errors.append("Invalid 'auth_mode'. Supported values: api_key, login.")
    elif auth_mode == "api_key":
        if not api_key:
            errors.append("auth_mode=api_key requires plugin setting 'api_key' (or 'unifi_api_key').")
    elif auth_mode == "login":
        if not username or not password:
            errors.append(
                "auth_mode=login requires plugin settings 'username'+'password' "
                "(or 'unifi_username'+'unifi_password')."
            )

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
    settings_data = normalize_plugin_settings(plugin_settings or get_plugin_settings())
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
