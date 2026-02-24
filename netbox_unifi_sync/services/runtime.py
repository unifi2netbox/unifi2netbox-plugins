from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from netbox_unifi2netbox.configuration import resolve_secret_value


@dataclass(frozen=True)
class ControllerRuntimeConfig:
    name: str
    base_url: str
    auth_mode: str
    api_key: str
    api_key_header: str
    username: str
    password: str
    mfa_secret: str
    verify_ssl: bool
    request_timeout: int
    http_retries: int
    retry_backoff_base: float
    retry_backoff_max: float


def _secret(ref: str) -> str:
    return str(resolve_secret_value(ref or "")).strip()


def to_controller_runtime(controller: Any, defaults: dict[str, Any]) -> ControllerRuntimeConfig:
    auth_mode = str(getattr(controller, "auth_mode", "") or "api_key").strip().lower()
    return ControllerRuntimeConfig(
        name=str(controller.name),
        base_url=str(controller.base_url).strip(),
        auth_mode=auth_mode,
        api_key=_secret(getattr(controller, "api_key_ref", "")),
        api_key_header=str(getattr(controller, "api_key_header", "X-API-KEY") or "X-API-KEY").strip(),
        username=_secret(getattr(controller, "username_ref", "")),
        password=_secret(getattr(controller, "password_ref", "")),
        mfa_secret=_secret(getattr(controller, "mfa_secret_ref", "")),
        verify_ssl=bool(getattr(controller, "verify_ssl", defaults.get("verify_ssl_default", True))),
        request_timeout=int(getattr(controller, "request_timeout", None) or defaults.get("request_timeout", 15)),
        http_retries=int(getattr(controller, "http_retries", None) or defaults.get("http_retries", 3)),
        retry_backoff_base=float(getattr(controller, "retry_backoff_base", None) or defaults.get("retry_backoff_base", 1.0)),
        retry_backoff_max=float(getattr(controller, "retry_backoff_max", None) or defaults.get("retry_backoff_max", 30.0)),
    )


def auth_signature(cfg: ControllerRuntimeConfig) -> tuple[str, ...]:
    return (
        cfg.auth_mode,
        cfg.api_key,
        cfg.api_key_header,
        cfg.username,
        cfg.password,
        cfg.mfa_secret,
        str(cfg.verify_ssl),
        str(cfg.request_timeout),
        str(cfg.http_retries),
        str(cfg.retry_backoff_base),
        str(cfg.retry_backoff_max),
    )


def group_runtimes_by_auth(configs: list[ControllerRuntimeConfig]) -> dict[tuple[str, ...], list[ControllerRuntimeConfig]]:
    grouped: dict[tuple[str, ...], list[ControllerRuntimeConfig]] = {}
    for cfg in configs:
        sig = auth_signature(cfg)
        grouped.setdefault(sig, []).append(cfg)
    return grouped


def redact_runtime(cfg: ControllerRuntimeConfig) -> dict[str, Any]:
    return {
        "name": cfg.name,
        "base_url": cfg.base_url,
        "auth_mode": cfg.auth_mode,
        "api_key": "***" if cfg.api_key else "",
        "username": "***" if cfg.username else "",
        "password": "***" if cfg.password else "",
        "mfa_secret": "***" if cfg.mfa_secret else "",
        "verify_ssl": cfg.verify_ssl,
        "request_timeout": cfg.request_timeout,
        "http_retries": cfg.http_retries,
        "retry_backoff_base": cfg.retry_backoff_base,
        "retry_backoff_max": cfg.retry_backoff_max,
    }
