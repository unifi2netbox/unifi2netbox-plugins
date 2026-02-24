from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("started", models.DateTimeField(blank=True, null=True)),
                ("completed", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("dry_run", "Dry Run"),
                        ],
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("trigger", models.CharField(default="manual", max_length=32)),
                ("dry_run", models.BooleanField(default=False)),
                ("job_id", models.CharField(blank=True, max_length=128)),
                ("controllers_total", models.PositiveIntegerField(default=0)),
                ("sites_total", models.PositiveIntegerField(default=0)),
                ("devices_total", models.PositiveIntegerField(default=0)),
                ("message", models.CharField(blank=True, max_length=255)),
                ("error", models.TextField(blank=True)),
                ("config_snapshot", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="unifi2netbox_sync_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created",),
                "permissions": (("run_sync", "Can trigger UniFi sync runs"),),
            },
        ),
    ]
