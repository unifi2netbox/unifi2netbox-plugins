from __future__ import annotations

from typing import Any

from netbox_unifi_sync.services.sync.log_sanitizer import redact_text


def record_event(*, action: str, status: str, actor=None, target: str = "", message: str = "", details: dict[str, Any] | None = None):
    from ..models import PluginAuditEvent

    PluginAuditEvent.objects.create(
        action=action,
        status=status,
        actor=actor,
        target=target,
        message=redact_text(str(message or ""))[:255],
        details=details or {},
    )


def sanitize_error(message: str) -> str:
    return redact_text(str(message or ""))
