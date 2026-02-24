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

    def ready(self):
        super().ready()
        from . import jobs  # noqa: F401


config = NetBoxUnifiSyncConfig
