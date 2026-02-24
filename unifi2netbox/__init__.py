"""
Compatibility plugin entrypoint.

Allows NetBox `PLUGINS = ["unifi2netbox"]` while the Django app label and
migration module remain `netbox_unifi2netbox`.
"""

from netbox_unifi2netbox import Unifi2NetBoxPluginConfig, config

__all__ = ["Unifi2NetBoxPluginConfig", "config"]
