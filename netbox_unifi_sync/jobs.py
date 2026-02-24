from __future__ import annotations

import logging
from typing import Any

from core.exceptions import JobFailed
from django.contrib.auth import get_user_model
from netbox.jobs import JobRunner, system_job

from .models import SyncRun
from .services.audit import record_event, sanitize_error
from .services.orchestrator import (
    SyncConfigurationError,
    get_or_create_global_settings,
    mark_scheduler_tick,
    run_sync,
    scheduler_due,
)

logger = logging.getLogger("netbox.plugins.netbox_unifi_sync.jobs")


def _resolve_user(user_id: Any):
    if not user_id:
        return None
    User = get_user_model()
    try:
        return User.objects.filter(pk=user_id).first()
    except Exception:
        return None


def _run_sync_job(*, dry_run: bool, cleanup_requested: bool, requested_by_id: int | None, trigger: str, job_id: str):
    run = SyncRun.objects.create(
        status="pending",
        dry_run=bool(dry_run),
        cleanup_requested=bool(cleanup_requested),
        trigger=trigger,
        requested_by=_resolve_user(requested_by_id),
        job_id=str(job_id or ""),
    )
    run.mark_running()

    try:
        result = run_sync(
            dry_run=bool(dry_run),
            cleanup_requested=bool(cleanup_requested),
            requested_by_id=requested_by_id,
        )
    except Exception as exc:
        safe_error = sanitize_error(str(exc))
        run.mark_failed(safe_error)
        record_event(
            action="sync.run",
            status="error",
            actor=run.requested_by,
            message=safe_error,
            details={"dry_run": dry_run, "cleanup_requested": cleanup_requested, "trigger": trigger},
        )
        raise

    summary = (
        f"mode={result.get('mode')} controllers={result.get('controllers', 0)} "
        f"sites={result.get('sites', 0)} devices={result.get('devices', 0)}"
    )
    run.mark_finished(result=result, dry_run=bool(dry_run), summary=summary)
    record_event(
        action="sync.run",
        status="success",
        actor=run.requested_by,
        message=summary,
        details={"dry_run": dry_run, "cleanup_requested": cleanup_requested, "trigger": trigger},
    )
    return {"sync_run_id": run.pk, **result}


class UnifiSyncJob(JobRunner):
    class Meta:
        name = "UniFi Sync"
        description = "Run UniFi synchronization inside NetBox"

    def run(self, dry_run: bool = False, cleanup_requested: bool = False, trigger: str = "manual", requested_by_id: int | None = None):
        self.logger.info("Starting UniFi sync job")
        try:
            result = _run_sync_job(
                dry_run=bool(dry_run),
                cleanup_requested=bool(cleanup_requested),
                requested_by_id=requested_by_id,
                trigger=trigger,
                job_id=str(getattr(self.job, "id", "") or getattr(self.job, "pk", "")),
            )
        except SyncConfigurationError as exc:
            raise JobFailed(f"Configuration error: {exc}") from exc
        except Exception as exc:
            raise JobFailed(f"Sync failed: {exc}") from exc

        self.logger.info("UniFi sync job completed")
        return result

    @classmethod
    def enqueue_sync(cls, *, user=None, dry_run: bool = False, cleanup_requested: bool = False, trigger: str = "manual-ui"):
        kwargs = {
            "dry_run": bool(dry_run),
            "cleanup_requested": bool(cleanup_requested),
            "trigger": trigger,
        }
        if user is not None and getattr(user, "pk", None):
            kwargs["requested_by_id"] = int(user.pk)
        return cls.enqueue(**kwargs)


@system_job(interval=60)
class UnifiSyncSchedulerJob(JobRunner):
    class Meta:
        name = "UniFi Sync Scheduler"
        description = "Runs every minute and triggers UniFi sync when interval is due"

    def run(self):
        settings = get_or_create_global_settings()
        if not scheduler_due(settings):
            return {"status": "skipped", "reason": "interval not due"}

        mark_scheduler_tick()
        return _run_sync_job(
            dry_run=bool(settings.dry_run_default),
            cleanup_requested=bool(settings.cleanup_enabled),
            requested_by_id=None,
            trigger="scheduler",
            job_id=str(getattr(self.job, "id", "") or getattr(self.job, "pk", "")),
        )


def enqueue_sync_job(*, user=None, dry_run: bool = False, cleanup_requested: bool = False, trigger: str = "manual-ui"):
    return UnifiSyncJob.enqueue_sync(
        user=user,
        dry_run=dry_run,
        cleanup_requested=cleanup_requested,
        trigger=trigger,
    )
