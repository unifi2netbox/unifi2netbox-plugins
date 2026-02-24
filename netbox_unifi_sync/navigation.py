from __future__ import annotations

from netbox.plugins import PluginMenuButton, PluginMenuItem


menu_items = (
    PluginMenuItem(
        link="plugins:netbox_unifi_sync:dashboard",
        link_text="Sync Dashboard",
        permissions=["netbox_unifi_sync.view_syncrun"],
        buttons=(
            PluginMenuButton(
                link="plugins:netbox_unifi_sync:dashboard",
                title="Run now",
                icon_class="mdi mdi-play-circle",
                permissions=["netbox_unifi_sync.run_sync"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_unifi_sync:controllers",
        link_text="Controllers",
        permissions=["netbox_unifi_sync.view_unificontroller"],
    ),
    PluginMenuItem(
        link="plugins:netbox_unifi_sync:mappings",
        link_text="Site mappings",
        permissions=["netbox_unifi_sync.view_sitemapping"],
    ),
    PluginMenuItem(
        link="plugins:netbox_unifi_sync:settings",
        link_text="Settings",
        permissions=["netbox_unifi_sync.change_globalsyncsettings"],
    ),
    PluginMenuItem(
        link="plugins:netbox_unifi_sync:runs",
        link_text="Run history",
        permissions=["netbox_unifi_sync.view_syncrun"],
    ),
    PluginMenuItem(
        link="plugins:netbox_unifi_sync:audit",
        link_text="Audit log",
        permissions=["netbox_unifi_sync.view_pluginauditevent"],
    ),
)
