from __future__ import annotations

import json
import logging

from django.core.management.base import BaseCommand, CommandError

from netbox_unifi2netbox.configuration import get_plugin_settings
from netbox_unifi2netbox.models import SyncRun
from netbox_unifi2netbox.services.sync_service import (
    build_config_snapshot,
    execute_sync,
    format_sync_summary,
)

logger = logging.getLogger("netbox.plugins.netbox_unifi2netbox.command")


class Command(BaseCommand):
    help = "Run UniFi -> NetBox synchronization once using plugin settings."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Run preflight checks only")
        parser.add_argument(
            "--trigger",
            default="management-command",
            help="Trigger label stored in SyncRun history",
        )
        parser.add_argument("--json", action="store_true", help="Output JSON result")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run", False))
        trigger = str(options.get("trigger") or "management-command")

        sync_run = SyncRun.objects.create(
            status="pending",
            dry_run=dry_run,
            trigger=trigger,
            config_snapshot=build_config_snapshot(get_plugin_settings()),
        )
        sync_run.mark_running()

        try:
            result = execute_sync(dry_run=dry_run)
        except Exception as exc:
            sync_run.mark_failed(str(exc))
            raise CommandError(str(exc)) from exc

        sync_run.mark_success(
            result,
            dry_run=dry_run,
            message=format_sync_summary(result),
        )

        if options.get("json"):
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        else:
            self.stdout.write(self.style.SUCCESS(format_sync_summary(result)))
