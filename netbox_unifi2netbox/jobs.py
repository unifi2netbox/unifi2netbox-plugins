from __future__ import annotations

import logging

from core.exceptions import JobFailed
from netbox.jobs import JobRunner, system_job

from main import run_sync_once

from .configuration import (
    get_plugin_settings,
    get_sync_interval_minutes,
    patched_environ,
    plugin_settings_to_env,
    validate_plugin_settings,
)


class Unifi2NetBoxSyncJob(JobRunner):
    class Meta:
        name = "UniFi -> NetBox sync"
        description = "Run one synchronization cycle from UniFi controllers into NetBox."

    def run(self, *args, **kwargs):
        logger = getattr(self, "logger", logging.getLogger(__name__))
        plugin_settings = get_plugin_settings()
        validation_errors = validate_plugin_settings(plugin_settings)
        if validation_errors:
            raise JobFailed(" ".join(validation_errors))

        env_values = plugin_settings_to_env(plugin_settings)
        logger.info("Starting UniFi -> NetBox sync job")
        try:
            with patched_environ(env_values):
                result = run_sync_once(clear_state=True)
        except SystemExit as exc:
            raise JobFailed(f"Sync aborted with exit code {exc.code}") from exc
        except Exception as exc:
            raise JobFailed(f"Sync failed: {exc}") from exc
        logger.info("UniFi -> NetBox sync completed")
        return result


_sync_interval = get_sync_interval_minutes()
if _sync_interval > 0:

    @system_job(interval=_sync_interval)
    class Unifi2NetBoxScheduledSyncJob(Unifi2NetBoxSyncJob):
        class Meta:
            name = "UniFi -> NetBox sync (scheduled)"
            description = "Scheduled synchronization cycle from UniFi controllers into NetBox."
