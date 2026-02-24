from __future__ import annotations

try:  # pragma: no cover - NetBox 4+
    from netbox.plugins import PluginMenuButton, PluginMenuItem
except Exception:  # pragma: no cover - NetBox 3.x
    from extras.plugins import PluginMenuButton, PluginMenuItem


status_buttons = [
    PluginMenuButton(
        link="plugins:netbox_unifi2netbox:status",
        title="Run Sync",
        icon_class="mdi mdi-play-circle",
        permissions=["netbox_unifi2netbox.run_sync"],
    )
]

menu_items = (
    PluginMenuItem(
        link="plugins:netbox_unifi2netbox:status",
        link_text="UniFi Sync Status",
        permissions=["netbox_unifi2netbox.view_syncrun"],
        buttons=status_buttons,
    ),
    PluginMenuItem(
        link="plugins:netbox_unifi2netbox:syncrun_list",
        link_text="Sync Runs",
        permissions=["netbox_unifi2netbox.view_syncrun"],
    ),
)
