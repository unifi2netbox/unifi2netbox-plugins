from __future__ import annotations

try:
    from netbox.plugins import PluginConfig
except ModuleNotFoundError:  # pragma: no cover
    class PluginConfig:  # type: ignore[no-redef]
        pass

from .version import __version__


class NetBoxUnifiSyncConfig(PluginConfig):
    name = "netbox_unifi_sync"
    label = "netbox_unifi_sync"
    verbose_name = "NetBox UniFi Sync"
    description = "In-platform UniFi to NetBox synchronization with scheduled jobs"
    version = __version__
    author = "Patrick Lind"
    base_url = "unifi-sync"
    min_version = "4.2.0"
    max_version = "4.99.99"
    default_settings = {}
    required_settings = []
    menu = "navigation.menu"
    menu_items = "navigation.empty_menu_items"

    def ready(self):
        super().ready()
        from . import jobs  # noqa: F401
        try:
            from netbox.models.features import register_models
            from .models import (
                GlobalSyncSettings,
                UnifiController,
                SiteMapping,
                SyncRun,
                PluginAuditEvent,
            )
            register_models(
                GlobalSyncSettings,
                UnifiController,
                SiteMapping,
                SyncRun,
                PluginAuditEvent,
            )
        except Exception:  # nosec B110 — intentional: unknown exception from NetBox plugin API
            pass  # graceful degradation when register_models is unavailable


config = NetBoxUnifiSyncConfig
