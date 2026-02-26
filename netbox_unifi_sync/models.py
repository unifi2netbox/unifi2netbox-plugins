from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

class AuthMode(models.TextChoices):
    API_KEY = "api_key", "API key"
    LOGIN = "login", "Login"


class VrfMode(models.TextChoices):
    NONE = "none", "None"
    EXISTING = "existing", "Existing"
    CREATE = "create", "Create"


class TagStrategy(models.TextChoices):
    APPEND = "append", "Append"
    REPLACE = "replace", "Replace"
    NONE = "none", "None"


class SyncRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    DRY_RUN = "dry_run", "Dry run"
    SKIPPED = "skipped", "Skipped"


class GlobalSyncSettings(models.Model):
    singleton_key = models.CharField(max_length=32, unique=True, default="default")

    enabled = models.BooleanField(default=True)
    tenant_name = models.CharField(max_length=100, help_text="Mandatory import tenant name in NetBox")
    default_vrf_name = models.CharField(max_length=100, blank=True)
    vrf_mode = models.CharField(max_length=16, choices=VrfMode.choices, default=VrfMode.EXISTING)

    serial_mode = models.CharField(max_length=24, default="mac")
    default_site = models.CharField(max_length=100, blank=True)
    tag_strategy = models.CharField(max_length=16, choices=TagStrategy.choices, default=TagStrategy.APPEND)
    default_tags = models.JSONField(default=list, blank=True)
    asset_tag_enabled = models.BooleanField(default=True)
    asset_tag_patterns = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON list of regex patterns. First match wins. Use capture group for extracted value.",
    )
    asset_tag_uppercase = models.BooleanField(default=True)

    netbox_roles = models.JSONField(
        default=dict,
        help_text="Map UniFi role keys to NetBox device role names",
    )

    sync_interfaces = models.BooleanField(default=True)
    sync_vlans = models.BooleanField(default=True)
    sync_wlans = models.BooleanField(default=True)
    sync_cables = models.BooleanField(default=True)
    sync_stale_cleanup = models.BooleanField(default=True)

    dhcp_auto_discover = models.BooleanField(default=True)
    dhcp_ranges = models.TextField(
        blank=True,
        default="",
        help_text="Manual DHCP ranges in CIDR notation, one per line (e.g. 192.168.1.0/24). "
                  "Merged with auto-discovered ranges.",
    )
    sync_dhcp_ranges = models.BooleanField(
        default=True,
        help_text="Sync DHCP IP ranges to NetBox IPAM.",
    )
    dhcp_writeback_enabled = models.BooleanField(default=False)

    default_gateway = models.GenericIPAddressField(
        protocol="IPv4",
        blank=True,
        null=True,
        help_text="Fallback gateway IP used for DHCP→static conversion when UniFi network config lacks a gateway.",
    )
    default_dns = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Fallback DNS servers, comma-separated (e.g. 8.8.8.8,8.8.4.4). "
                  "Used when UniFi network config lacks DNS information.",
    )

    netbox_device_status = models.CharField(
        max_length=32,
        default="planned",
        help_text="Status assigned to newly created devices in NetBox "
                  "(e.g. planned, staged, active, inventory).",
    )
    sync_prefixes = models.BooleanField(
        default=True,
        help_text="Sync network prefixes from UniFi to NetBox IPAM.",
    )

    cleanup_enabled = models.BooleanField(default=False)
    cleanup_grace_days = models.PositiveIntegerField(default=30)

    schedule_enabled = models.BooleanField(default=False)
    sync_interval_minutes = models.PositiveIntegerField(default=60)
    dry_run_default = models.BooleanField(default=False)

    verify_ssl_default = models.BooleanField(default=True)
    request_timeout = models.PositiveIntegerField(default=15)
    http_retries = models.PositiveIntegerField(default=3)
    retry_backoff_base = models.FloatField(default=1.0)
    retry_backoff_max = models.FloatField(default=30.0)

    max_controller_threads = models.PositiveIntegerField(default=5)
    max_site_threads = models.PositiveIntegerField(default=8)
    max_device_threads = models.PositiveIntegerField(default=8)
    rate_limit_per_second = models.PositiveIntegerField(default=0)

    specs_auto_refresh = models.BooleanField(default=False)
    specs_include_store = models.BooleanField(default=False)
    specs_refresh_timeout = models.PositiveIntegerField(default=45)
    specs_store_timeout = models.PositiveIntegerField(default=15)
    specs_store_max_workers = models.PositiveIntegerField(default=8)
    specs_write_cache = models.BooleanField(default=False)

    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("singleton_key",)
        verbose_name = "UniFi sync settings"
        permissions = (
            ("run_sync", "Can trigger UniFi sync"),
            ("run_cleanup", "Can trigger UniFi cleanup"),
            ("test_controller", "Can test UniFi controller connectivity"),
        )

    def __str__(self) -> str:
        return "Global UniFi sync settings"

    def clean(self):
        errors = {}
        if not self.tenant_name.strip():
            errors["tenant_name"] = "tenant_name is required."
        if self.sync_interval_minutes < 1:
            errors["sync_interval_minutes"] = "sync_interval_minutes must be >= 1."
        if self.retry_backoff_base <= 0:
            errors["retry_backoff_base"] = "retry_backoff_base must be > 0."
        if self.retry_backoff_max < self.retry_backoff_base:
            errors["retry_backoff_max"] = "retry_backoff_max must be >= retry_backoff_base."
        if not isinstance(self.default_tags, list):
            errors["default_tags"] = "default_tags must be a JSON list."
        if not isinstance(self.asset_tag_patterns, list):
            errors["asset_tag_patterns"] = "asset_tag_patterns must be a JSON list."
        else:
            for idx, pattern in enumerate(self.asset_tag_patterns):
                text = str(pattern or "").strip()
                if not text:
                    errors["asset_tag_patterns"] = f"asset_tag_patterns[{idx}] cannot be empty."
                    break
                try:
                    re.compile(text)
                except re.error as exc:
                    errors["asset_tag_patterns"] = f"Invalid regex in asset_tag_patterns[{idx}]: {exc}"
                    break
        if not isinstance(self.netbox_roles, dict) or not self.netbox_roles:
            errors["netbox_roles"] = "netbox_roles must be a non-empty JSON object."
        if errors:
            raise ValidationError(errors)


class UnifiController(models.Model):
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(max_length=255, unique=True)
    enabled = models.BooleanField(default=True)

    auth_mode = models.CharField(max_length=16, choices=AuthMode.choices, default=AuthMode.API_KEY)
    api_key_ref = models.CharField(max_length=255, blank=True, help_text="Use env:VAR_NAME or file:/path")
    api_key_header = models.CharField(max_length=64, default="X-API-KEY")
    username_ref = models.CharField(max_length=255, blank=True, help_text="Use env:VAR_NAME or file:/path")
    password_ref = models.CharField(max_length=255, blank=True, help_text="Use env:VAR_NAME or file:/path")
    mfa_secret_ref = models.CharField(max_length=255, blank=True, help_text="Use env:VAR_NAME or file:/path")

    verify_ssl = models.BooleanField(default=True)
    request_timeout = models.PositiveIntegerField(null=True, blank=True)
    http_retries = models.PositiveIntegerField(null=True, blank=True)
    retry_backoff_base = models.FloatField(null=True, blank=True)
    retry_backoff_max = models.FloatField(null=True, blank=True)

    notes = models.TextField(blank=True)
    last_tested = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=16, blank=True)
    last_test_error = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def clean(self):
        errors = {}
        self.api_key_ref = (self.api_key_ref or "").strip()
        self.username_ref = (self.username_ref or "").strip()
        self.password_ref = (self.password_ref or "").strip()
        self.mfa_secret_ref = (self.mfa_secret_ref or "").strip()

        # Allow saving controller definitions before credentials are wired in.
        # Runtime sync/test enforces auth requirements for the selected mode.
        if self.auth_mode == AuthMode.LOGIN:
            if self.username_ref and not self.password_ref:
                errors["password_ref"] = "password_ref is required when username_ref is set for auth_mode=login"
            if self.password_ref and not self.username_ref:
                errors["username_ref"] = "username_ref is required when password_ref is set for auth_mode=login"

        if self.retry_backoff_base is not None and self.retry_backoff_base <= 0:
            errors["retry_backoff_base"] = "retry_backoff_base must be > 0"
        if self.retry_backoff_max is not None and self.retry_backoff_base is not None:
            if self.retry_backoff_max < self.retry_backoff_base:
                errors["retry_backoff_max"] = "retry_backoff_max must be >= retry_backoff_base"

        if errors:
            raise ValidationError(errors)


class SiteMapping(models.Model):
    controller = models.ForeignKey(
        UnifiController,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="site_mappings",
        help_text="Leave empty to apply mapping globally",
    )
    unifi_site = models.CharField(max_length=100)
    netbox_site = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("unifi_site",)
        unique_together = (("controller", "unifi_site"),)

    def __str__(self) -> str:
        scope = self.controller.name if self.controller else "global"
        return f"{scope}: {self.unifi_site} -> {self.netbox_site}"


class SyncRun(models.Model):
    status = models.CharField(max_length=24, choices=SyncRunStatus.choices, default=SyncRunStatus.PENDING)
    trigger = models.CharField(max_length=32, default="manual")
    dry_run = models.BooleanField(default=False)
    cleanup_requested = models.BooleanField(default=False)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="netbox_unifi_sync_runs",
    )
    job_id = models.CharField(max_length=128, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    controllers_total = models.PositiveIntegerField(default=0)
    sites_total = models.PositiveIntegerField(default=0)
    devices_total = models.PositiveIntegerField(default=0)

    summary = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    counters = models.JSONField(default=dict, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created",)

    def __str__(self) -> str:
        return f"SyncRun#{self.pk} ({self.status})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_unifi_sync:run_detail", args=[self.pk])

    def mark_running(self):
        self.status = SyncRunStatus.RUNNING
        self.started = timezone.now()
        self.save(update_fields=["status", "started"])

    def mark_finished(self, *, result: dict, dry_run: bool, summary: str):
        self.details = result
        self.counters = {
            "controllers": int(result.get("controllers", 0) or 0),
            "sites": int(result.get("sites", 0) or 0),
            "devices": int(result.get("devices", 0) or 0),
        }
        self.controllers_total = self.counters["controllers"]
        self.sites_total = self.counters["sites"]
        self.devices_total = self.counters["devices"]
        self.summary = summary
        self.completed = timezone.now()
        if self.started:
            self.duration_ms = max(0, int((self.completed - self.started).total_seconds() * 1000))
        self.status = SyncRunStatus.DRY_RUN if dry_run else SyncRunStatus.SUCCESS
        self.save(
            update_fields=[
                "details",
                "counters",
                "controllers_total",
                "sites_total",
                "devices_total",
                "summary",
                "completed",
                "duration_ms",
                "status",
            ]
        )

    def mark_failed(self, message: str):
        self.status = SyncRunStatus.FAILED
        self.error = str(message or "")
        self.completed = timezone.now()
        if self.started:
            self.duration_ms = max(0, int((self.completed - self.started).total_seconds() * 1000))
        self.save(update_fields=["status", "error", "completed", "duration_ms"])


class SchedulerState(models.Model):
    key = models.CharField(max_length=32, unique=True, default="default")
    last_auto_sync = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"SchedulerState({self.key})"


class SpecsCacheMetadata(models.Model):
    source = models.CharField(max_length=64, unique=True)
    etag = models.CharField(max_length=255, blank=True)
    last_refresh = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("source",)

    def __str__(self) -> str:
        return self.source


class PluginAuditEvent(models.Model):
    ACTION_STATUS = (
        ("success", "Success"),
        ("error", "Error"),
    )

    created = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=ACTION_STATUS)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="netbox_unifi_sync_audit_events",
    )
    target = models.CharField(max_length=128, blank=True)
    message = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created",)

    def __str__(self) -> str:
        return f"{self.action} ({self.status})"
