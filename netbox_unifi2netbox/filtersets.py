from __future__ import annotations

import django_filters

from .models import SyncRun


class SyncRunFilterSet(django_filters.FilterSet):
    created = django_filters.DateFromToRangeFilter()
    status = django_filters.CharFilter(field_name="status")
    dry_run = django_filters.BooleanFilter(field_name="dry_run")

    class Meta:
        model = SyncRun
        fields = ["status", "dry_run", "created"]
