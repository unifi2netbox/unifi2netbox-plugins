from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from netbox_unifi_sync.services.unifi.unifi import Unifi

from ..configuration import resolve_secret_value

logger = logging.getLogger("netbox.plugins.netbox_unifi_sync.auth")


class UnifiAuthError(ValueError):
    """Raised for invalid UniFi auth settings."""


@dataclass(frozen=True)
class UnifiAuthSettings:
    auth_mode: str
    api_key: str
    api_key_header: str
    username: str
    password: str
    mfa_secret: str
    verify_ssl: bool = True

    @classmethod
    def from_plugin_settings(cls, plugin_settings: dict[str, Any]) -> "UnifiAuthSettings":
        auth_mode = str(plugin_settings.get("auth_mode") or "api_key").strip().lower()
        api_key = str(resolve_secret_value(plugin_settings.get("unifi_api_key") or "")).strip()
        api_key_header = str(resolve_secret_value(plugin_settings.get("unifi_api_key_header") or "X-API-KEY")).strip()
        username = str(resolve_secret_value(plugin_settings.get("unifi_username") or "")).strip()
        password = str(resolve_secret_value(plugin_settings.get("unifi_password") or "")).strip()
        mfa_secret = str(resolve_secret_value(plugin_settings.get("unifi_mfa_secret") or "")).strip()
        verify_ssl_raw = plugin_settings.get("verify_ssl")
        verify_ssl = bool(verify_ssl_raw) if verify_ssl_raw is not None else True
        return cls(
            auth_mode=auth_mode,
            api_key=api_key,
            api_key_header=api_key_header,
            username=username,
            password=password,
            mfa_secret=mfa_secret,
            verify_ssl=verify_ssl,
        )

    def validate(self) -> None:
        if self.auth_mode not in {"api_key", "login"}:
            raise UnifiAuthError("Invalid auth_mode. Supported values: api_key, login.")
        if self.auth_mode == "api_key" and not self.api_key:
            raise UnifiAuthError("auth_mode=api_key requires api_key.")
        if self.auth_mode == "login":
            if not self.username or not self.password:
                raise UnifiAuthError("auth_mode=login requires username and password.")

    def build_client(self, *, base_url: str) -> Unifi:
        self.validate()
        if self.auth_mode == "api_key":
            logger.debug("Building UniFi client using API key auth")
            return Unifi(
                base_url=base_url,
                api_key=self.api_key,
                api_key_header=self.api_key_header or "X-API-KEY",
                allow_login_fallback=False,
                verify_ssl=self.verify_ssl,
            )
        logger.debug("Building UniFi client using login auth")
        return Unifi(
            base_url=base_url,
            username=self.username,
            password=self.password,
            mfa_secret=self.mfa_secret or None,
            verify_ssl=self.verify_ssl,
        )
