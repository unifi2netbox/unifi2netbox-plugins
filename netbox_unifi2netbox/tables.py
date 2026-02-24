from __future__ import annotations

import django_tables2 as tables

try:  # pragma: no cover - runtime compatibility (NetBox)
    from netbox.tables import NetBoxTable
except Exception:  # pragma: no cover
    NetBoxTable = tables.Table

from .models import SyncRun


class SyncRunTable(NetBoxTable):
    created = tables.DateTimeColumn()
    started = tables.DateTimeColumn()
    completed = tables.DateTimeColumn()
    status = tables.Column(linkify=True)
    dry_run = tables.BooleanColumn()
    trigger = tables.Column()
    controllers_total = tables.Column(verbose_name="Controllers")
    sites_total = tables.Column(verbose_name="Sites")
    devices_total = tables.Column(verbose_name="Devices")

    class Meta:
        model = SyncRun
        fields = (
            "id",
            "created",
            "started",
            "completed",
            "status",
            "dry_run",
            "trigger",
            "controllers_total",
            "sites_total",
            "devices_total",
            "message",
        )
        default_columns = (
            "id",
            "created",
            "status",
            "dry_run",
            "trigger",
            "controllers_total",
            "sites_total",
            "devices_total",
            "message",
        )
