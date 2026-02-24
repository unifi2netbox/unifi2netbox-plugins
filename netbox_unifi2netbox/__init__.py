from __future__ import annotations

try:
    from netbox.plugins import PluginConfig
except ModuleNotFoundError:  # pragma: no cover - local unit tests without NetBox installed
    class PluginConfig:  # type: ignore[no-redef]
        pass

from .configuration import DEFAULT_SETTINGS


class Unifi2NetBoxPluginConfig(PluginConfig):
    name = "netbox_unifi2netbox"
    label = "unifi2netbox"
    verbose_name = "UniFi2NetBox"
    description = "Synchronize UniFi inventory into NetBox"
    version = "0.2.0"
    author = "Patrick Lind"
    base_url = "unifi2netbox"
    min_version = "4.0.0"
    default_settings = DEFAULT_SETTINGS
    required_settings = []

    def ready(self):
        super().ready()
        from . import jobs  # noqa: F401


config = Unifi2NetBoxPluginConfig
