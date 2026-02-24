from __future__ import annotations

from django import forms

from .models import SyncRunStatus


class SyncTriggerForm(forms.Form):
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label="Dry run",
        help_text="When enabled, run preflight checks only and skip synchronization writes.",
    )


class SyncRunFilterForm(forms.Form):
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Any"), *SyncRunStatus.choices],
        label="Status",
    )
    dry_run = forms.ChoiceField(
        required=False,
        choices=[("", "Any"), ("true", "Dry run"), ("false", "Real sync")],
        label="Mode",
    )
    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search in message/error text.",
    )
    limit = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=500,
        initial=100,
        label="Limit",
    )
