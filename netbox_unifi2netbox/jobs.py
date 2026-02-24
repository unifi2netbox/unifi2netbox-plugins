from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model

from .configuration import get_plugin_settings, get_sync_interval_minutes
from .models import SyncRun
from .services.sync_service import build_config_snapshot, execute_sync, format_sync_summary

logger = logging.getLogger("netbox.plugins.netbox_unifi2netbox.jobs")


def _resolve_user(user_id: Any):
    if not user_id:
        return None
    User = get_user_model()
    try:
        return User.objects.filter(pk=user_id).first()
    except Exception:
        return None


def _run_sync_job(
    *,
    dry_run: bool = False,
    trigger: str = "job",
    requested_by_id: int | None = None,
    job_id: str = "",
):
    plugin_settings = get_plugin_settings()
    sync_run = SyncRun.objects.create(
        status="pending",
        dry_run=bool(dry_run),
        trigger=trigger,
        requested_by=_resolve_user(requested_by_id),
        job_id=str(job_id or ""),
        config_snapshot=build_config_snapshot(plugin_settings),
    )
    sync_run.mark_running()

    try:
        result = execute_sync(dry_run=bool(dry_run))
    except Exception as exc:
        sync_run.mark_failed(str(exc))
        raise

    sync_run.mark_success(
        result,
        dry_run=bool(dry_run),
        message=format_sync_summary(result),
    )
    return {
        "sync_run_id": sync_run.pk,
        **result,
    }


HAS_JOBRUNNER = True
try:
    from core.exceptions import JobFailed
    from netbox.jobs import JobRunner, system_job
except Exception:  # pragma: no cover
    HAS_JOBRUNNER = False


if HAS_JOBRUNNER:

    class Unifi2NetBoxSyncJob(JobRunner):
        class Meta:
            name = "UniFi -> NetBox Sync"
            description = "Synchronize UniFi controllers into NetBox."

        def run(self, dry_run: bool = False, trigger: str = "job", requested_by_id: int | None = None):
            self.logger.info("Starting UniFi sync job")
            try:
                result = _run_sync_job(
                    dry_run=bool(dry_run),
                    trigger=trigger,
                    requested_by_id=requested_by_id,
                    job_id=str(getattr(self.job, "pk", "") or getattr(self.job, "id", "")),
                )
            except Exception as exc:
                raise JobFailed(f"Sync failed: {exc}") from exc
            self.logger.info("UniFi sync job completed")
            return result

        @classmethod
        def enqueue_sync(cls, *, user=None, dry_run: bool = False, trigger: str = "manual-ui"):
            kwargs = {
                "dry_run": bool(dry_run),
                "trigger": trigger,
            }
            if user is not None and getattr(user, "pk", None):
                kwargs["requested_by_id"] = int(user.pk)
            return cls.enqueue(**kwargs)


    _sync_interval = get_sync_interval_minutes()
    if _sync_interval > 0:

        @system_job(interval=_sync_interval)
        class Unifi2NetBoxScheduledSyncJob(Unifi2NetBoxSyncJob):
            class Meta:
                name = "UniFi -> NetBox Sync (Scheduled)"
                description = "Scheduled synchronization from UniFi controllers into NetBox."

else:  # pragma: no cover - NetBox 3.x compatibility path
    try:
        from extras.jobs import Job, register_jobs
        from extras.scripts import BooleanVar
    except Exception as exc:
        raise RuntimeError("No supported NetBox jobs framework found.") from exc

    class Unifi2NetBoxSyncJob(Job):
        class Meta:
            name = "UniFi -> NetBox Sync"
            description = "Synchronize UniFi controllers into NetBox."

        dry_run = BooleanVar(description="Run preflight checks only", default=False)

        def run(self, data, commit=True):
            dry_run = bool((data or {}).get("dry_run", False))
            return _run_sync_job(dry_run=dry_run, trigger="legacy-job")

    register_jobs(Unifi2NetBoxSyncJob)


def enqueue_sync_job(*, user=None, dry_run: bool = False, trigger: str = "manual-ui"):
    """
    Enqueue a sync job from plugin UI.

    On NetBox versions without JobRunner enqueue support, this raises RuntimeError
    and users should trigger the job from the Jobs UI instead.
    """
    if HAS_JOBRUNNER and hasattr(Unifi2NetBoxSyncJob, "enqueue_sync"):
        return Unifi2NetBoxSyncJob.enqueue_sync(user=user, dry_run=dry_run, trigger=trigger)

    raise RuntimeError("Programmatic job enqueue is not available on this NetBox version.")
