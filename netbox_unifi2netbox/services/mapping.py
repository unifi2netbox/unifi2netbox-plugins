from __future__ import annotations

from typing import Iterable


def resolve_site_name(unifi_site_name: str, site_mappings: dict[str, str], default_site_name: str = "") -> str:
    """Resolve UniFi site name using explicit mapping and optional default fallback."""
    source = str(unifi_site_name or "").strip()
    if not source:
        return str(default_site_name or "").strip()

    normalized_mappings = {
        str(key).strip(): str(value).strip()
        for key, value in (site_mappings or {}).items()
        if str(key).strip() and str(value).strip()
    }
    if source in normalized_mappings:
        return normalized_mappings[source]
    return source or str(default_site_name or "").strip()


def merge_tags(existing: Iterable[str], defaults: Iterable[str], strategy: str = "append") -> list[str]:
    """
    Merge tags using strategy:
    - append: existing + defaults (de-duplicated)
    - replace: defaults only
    - none: existing only
    """
    existing_tags = [str(tag).strip() for tag in (existing or []) if str(tag).strip()]
    default_tags = [str(tag).strip() for tag in (defaults or []) if str(tag).strip()]

    mode = str(strategy or "append").strip().lower()
    if mode == "replace":
        source = default_tags
    elif mode == "none":
        source = existing_tags
    else:
        source = [*existing_tags, *default_tags]

    unique: list[str] = []
    seen = set()
    for tag in source:
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(tag)
    return unique


def format_result_summary(raw: dict | None, dry_run: bool = False) -> dict:
    result = raw or {}
    return {
        "mode": "dry-run" if dry_run else "sync",
        "controllers": int(result.get("controllers", 0) or 0),
        "sites": int(result.get("sites", 0) or 0),
        "devices": int(result.get("devices", 0) or 0),
        "details": result,
    }
