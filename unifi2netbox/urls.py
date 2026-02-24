"""
URL shim for NetBox plugin discovery.

NetBox registers plugin URL patterns by importing `<plugin_path>.urls`.
This package is configured as `PLUGINS = ["unifi2netbox"]`, while the
implementation lives in `netbox_unifi2netbox`.
"""

from netbox_unifi2netbox.urls import urlpatterns

app_name = "unifi2netbox"
