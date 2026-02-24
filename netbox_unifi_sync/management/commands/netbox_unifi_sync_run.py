from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from netbox_unifi_sync.jobs import _run_sync_job


class Command(BaseCommand):
    help = "Run NetBox UniFi sync once (inside NetBox runtime)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--cleanup", action="store_true")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        try:
            result = _run_sync_job(
                dry_run=bool(options.get("dry_run")),
                cleanup_requested=bool(options.get("cleanup")),
                requested_by_id=None,
                trigger="management-command",
                job_id="",
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        if options.get("json"):
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"mode={result.get('mode')} controllers={result.get('controllers')} sites={result.get('sites')} devices={result.get('devices')}"
                )
            )
