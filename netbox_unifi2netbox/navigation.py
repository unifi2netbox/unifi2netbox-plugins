from __future__ import annotations

from netbox.plugins import PluginMenuButton, PluginMenuItem


status_buttons = [
    PluginMenuButton(
        link="plugins:unifi2netbox:status",
        title="Run Sync",
        icon_class="mdi mdi-play-circle",
        permissions=["unifi2netbox.run_sync"],
    )
]

menu_items = (
    PluginMenuItem(
        link="plugins:unifi2netbox:status",
        link_text="UniFi Sync Status",
        permissions=["unifi2netbox.view_syncrun"],
        buttons=status_buttons,
    ),
    PluginMenuItem(
        link="plugins:unifi2netbox:syncrun_list",
        link_text="Sync Runs",
        permissions=["unifi2netbox.view_syncrun"],
    ),
)
