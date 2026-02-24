from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class SyncRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    DRY_RUN = "dry_run", "Dry Run"


class SyncRun(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(blank=True, null=True)
    completed = models.DateTimeField(blank=True, null=True)

    status = models.CharField(max_length=24, choices=SyncRunStatus.choices, default=SyncRunStatus.PENDING)
    trigger = models.CharField(max_length=32, default="manual")
    dry_run = models.BooleanField(default=False)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="unifi2netbox_sync_runs",
    )
    job_id = models.CharField(max_length=128, blank=True)

    controllers_total = models.PositiveIntegerField(default=0)
    sites_total = models.PositiveIntegerField(default=0)
    devices_total = models.PositiveIntegerField(default=0)

    message = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    config_snapshot = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created",)
        permissions = (
            ("run_sync", "Can trigger UniFi sync runs"),
        )

    def __str__(self) -> str:
        return f"SyncRun#{self.pk} ({self.status})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_unifi2netbox:syncrun_detail", args=[self.pk])

    def mark_running(self):
        self.status = SyncRunStatus.RUNNING
        self.started = timezone.now()
        self.save(update_fields=["status", "started"])

    def mark_success(self, result: dict, *, dry_run: bool = False, message: str = ""):
        self.result = result or {}
        self.controllers_total = int(result.get("controllers", 0) or 0)
        self.sites_total = int(result.get("sites", 0) or 0)
        self.devices_total = int(result.get("devices", 0) or 0)
        self.message = message
        self.status = SyncRunStatus.DRY_RUN if dry_run else SyncRunStatus.SUCCESS
        self.completed = timezone.now()
        self.save(
            update_fields=[
                "result",
                "controllers_total",
                "sites_total",
                "devices_total",
                "message",
                "status",
                "completed",
            ]
        )

    def mark_failed(self, error: str):
        self.status = SyncRunStatus.FAILED
        self.error = str(error or "")
        self.completed = timezone.now()
        self.save(update_fields=["status", "error", "completed"])
