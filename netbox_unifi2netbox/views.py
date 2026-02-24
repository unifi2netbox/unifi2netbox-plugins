from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SyncRunFilterForm, SyncTriggerForm
from .jobs import enqueue_sync_job
from .models import SyncRun
from .services.sync_service import build_config_snapshot
from .configuration import get_plugin_settings


@login_required
@permission_required("unifi2netbox.view_syncrun", raise_exception=True)
def status_view(request: HttpRequest) -> HttpResponse:
    latest_run = SyncRun.objects.order_by("-created").first()
    recent_runs = SyncRun.objects.order_by("-created")[:10]

    trigger_form = SyncTriggerForm(initial={"dry_run": bool(get_plugin_settings().get("dry_run_default", False))})

    if request.method == "POST":
        if not request.user.has_perm("unifi2netbox.run_sync"):
            return HttpResponseForbidden("Missing permission: unifi2netbox.run_sync")

        trigger_form = SyncTriggerForm(request.POST)
        if trigger_form.is_valid():
            dry_run = bool(trigger_form.cleaned_data["dry_run"])
            try:
                job = enqueue_sync_job(user=request.user, dry_run=dry_run, trigger="plugin-ui")
            except Exception as exc:
                messages.error(request, f"Failed to queue sync job: {exc}")
            else:
                job_identifier = getattr(job, "id", None) or getattr(job, "pk", None) or "queued"
                mode = "dry run" if dry_run else "full sync"
                messages.success(request, f"Queued {mode} job ({job_identifier}).")
            return redirect("plugins:unifi2netbox:status")

    context = {
        "latest_run": latest_run,
        "recent_runs": recent_runs,
        "trigger_form": trigger_form,
        "plugin_settings": build_config_snapshot(get_plugin_settings()),
    }
    return render(request, "netbox_unifi2netbox/status.html", context)


@login_required
@permission_required("unifi2netbox.view_syncrun", raise_exception=True)
def syncrun_list_view(request: HttpRequest) -> HttpResponse:
    queryset = SyncRun.objects.order_by("-created")
    filter_form = SyncRunFilterForm(request.GET)

    if filter_form.is_valid():
        status = (filter_form.cleaned_data.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)

        dry_run = (filter_form.cleaned_data.get("dry_run") or "").strip().lower()
        if dry_run == "true":
            queryset = queryset.filter(dry_run=True)
        elif dry_run == "false":
            queryset = queryset.filter(dry_run=False)

        query = (filter_form.cleaned_data.get("q") or "").strip()
        if query:
            queryset = queryset.filter(Q(message__icontains=query) | Q(error__icontains=query))

        limit = filter_form.cleaned_data.get("limit") or 100
    else:
        limit = 100

    runs = queryset[:limit]
    return render(
        request,
        "netbox_unifi2netbox/syncrun_list.html",
        {
            "runs": runs,
            "filter_form": filter_form,
            "total_count": queryset.count(),
            "shown_count": len(runs),
        },
    )


@login_required
@permission_required("unifi2netbox.view_syncrun", raise_exception=True)
def syncrun_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    run = get_object_or_404(SyncRun, pk=pk)
    return render(request, "netbox_unifi2netbox/syncrun_detail.html", {"run": run})
