from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    GlobalSyncSettingsForm,
    RunActionForm,
    RunFilterForm,
    SiteMappingForm,
    UnifiControllerForm,
)
from .jobs import enqueue_sync_job
from .models import PluginAuditEvent, SiteMapping, SyncRun, UnifiController
from .services.audit import record_event, sanitize_error
from .services.orchestrator import (
    get_or_create_global_settings,
    test_controller_connection,
)


@login_required
@permission_required("netbox_unifi_sync.view_syncrun", raise_exception=True)
def dashboard_view(request: HttpRequest) -> HttpResponse:
    settings_obj = get_or_create_global_settings()
    latest_run = SyncRun.objects.order_by("-created").first()
    recent_runs = SyncRun.objects.order_by("-created")[:10]

    form = RunActionForm(initial={"dry_run": settings_obj.dry_run_default, "cleanup": settings_obj.cleanup_enabled})
    if request.method == "POST":
        if not request.user.has_perm("netbox_unifi_sync.run_sync"):
            return HttpResponseForbidden("Missing permission: netbox_unifi_sync.run_sync")
        form = RunActionForm(request.POST)
        if form.is_valid():
            dry_run = bool(form.cleaned_data.get("dry_run"))
            cleanup = bool(form.cleaned_data.get("cleanup"))
            try:
                job = enqueue_sync_job(
                    user=request.user,
                    dry_run=dry_run,
                    cleanup_requested=cleanup,
                    trigger="plugin-ui",
                )
            except Exception as exc:
                safe = sanitize_error(str(exc))
                messages.error(request, f"Failed to queue sync job: {safe}")
                record_event(
                    action="sync.enqueue",
                    status="error",
                    actor=request.user,
                    message=safe,
                    details={"dry_run": dry_run, "cleanup": cleanup},
                )
            else:
                identifier = getattr(job, "id", None) or getattr(job, "pk", None) or "queued"
                messages.success(request, f"Queued sync job ({identifier}).")
                record_event(
                    action="sync.enqueue",
                    status="success",
                    actor=request.user,
                    message="sync job queued",
                    details={"dry_run": dry_run, "cleanup": cleanup, "job": str(identifier)},
                )
            return redirect("plugins:netbox_unifi_sync:dashboard")

    context = {
        "settings": settings_obj,
        "latest_run": latest_run,
        "recent_runs": recent_runs,
        "form": form,
        "controller_count": UnifiController.objects.filter(enabled=True).count(),
    }
    return render(request, "netbox_unifi_sync/dashboard.html", context)


@login_required
@permission_required("netbox_unifi_sync.change_globalsyncsettings", raise_exception=True)
def settings_view(request: HttpRequest) -> HttpResponse:
    settings_obj = get_or_create_global_settings()
    form = GlobalSyncSettingsForm(instance=settings_obj)

    if request.method == "POST":
        form = GlobalSyncSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            record_event(action="settings.update", status="success", actor=request.user, message="Global settings updated")
            messages.success(request, "Global settings updated")
            return redirect("plugins:netbox_unifi_sync:settings")
        messages.error(request, "Unable to save settings. Fix validation errors.")

    return render(request, "netbox_unifi_sync/settings.html", {"form": form, "settings": settings_obj})


@login_required
@permission_required("netbox_unifi_sync.view_unificontroller", raise_exception=True)
def controller_list_view(request: HttpRequest) -> HttpResponse:
    controllers = UnifiController.objects.order_by("name")
    return render(request, "netbox_unifi_sync/controllers.html", {"controllers": controllers})


@login_required
@permission_required("netbox_unifi_sync.change_unificontroller", raise_exception=True)
def controller_edit_view(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    controller = get_object_or_404(UnifiController, pk=pk) if pk else None
    form = UnifiControllerForm(instance=controller)

    if request.method == "POST":
        form = UnifiControllerForm(request.POST, instance=controller)
        if form.is_valid():
            obj = form.save()
            action = "controller.update" if controller else "controller.create"
            record_event(action=action, status="success", actor=request.user, target=obj.name, message=f"{obj.name} saved")
            messages.success(request, f"Controller '{obj.name}' saved")
            return redirect("plugins:netbox_unifi_sync:controllers")
        messages.error(request, "Unable to save controller. Fix validation errors.")

    return render(request, "netbox_unifi_sync/controller_form.html", {"form": form, "controller": controller})


@login_required
@permission_required("netbox_unifi_sync.delete_unificontroller", raise_exception=True)
def controller_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    controller = get_object_or_404(UnifiController, pk=pk)
    if request.method == "POST":
        name = controller.name
        controller.delete()
        messages.success(request, f"Controller '{name}' deleted")
        record_event(action="controller.delete", status="success", actor=request.user, target=name, message=f"{name} deleted")
        return redirect("plugins:netbox_unifi_sync:controllers")
    return render(request, "netbox_unifi_sync/controller_delete.html", {"controller": controller})


@login_required
@permission_required("netbox_unifi_sync.test_controller", raise_exception=True)
def controller_test_view(request: HttpRequest, pk: int) -> HttpResponse:
    controller = get_object_or_404(UnifiController, pk=pk)
    settings_obj = get_or_create_global_settings()
    try:
        result = test_controller_connection(controller, settings_obj)
        controller.last_tested = timezone.now()
        controller.last_test_status = "ok"
        controller.last_test_error = ""
        controller.save(update_fields=["last_test_status", "last_test_error", "last_tested"])
        messages.success(request, f"Controller '{controller.name}' test OK. Sites: {result['sites']}")
        record_event(action="controller.test", status="success", actor=request.user, target=controller.name, message="Controller test succeeded", details=result)
    except Exception as exc:
        safe = sanitize_error(str(exc))
        controller.last_test_status = "error"
        controller.last_test_error = safe
        controller.save(update_fields=["last_test_status", "last_test_error", "updated"])
        messages.error(request, f"Controller test failed: {safe}")
        record_event(action="controller.test", status="error", actor=request.user, target=controller.name, message=safe)
    return redirect("plugins:netbox_unifi_sync:controllers")


@login_required
@permission_required("netbox_unifi_sync.test_controller", raise_exception=True)
def controller_test_api_view(request: HttpRequest, pk: int) -> JsonResponse:
    controller = get_object_or_404(UnifiController, pk=pk)
    settings_obj = get_or_create_global_settings()
    try:
        result = test_controller_connection(controller, settings_obj)
        controller.last_test_status = "ok"
        controller.last_test_error = ""
        controller.last_tested = timezone.now()
        controller.save(update_fields=["last_test_status", "last_test_error", "last_tested"])
        return JsonResponse(result, status=200)
    except Exception as exc:
        safe = sanitize_error(str(exc))
        controller.last_test_status = "error"
        controller.last_test_error = safe
        controller.last_tested = timezone.now()
        controller.save(update_fields=["last_test_status", "last_test_error", "last_tested"])
        return JsonResponse({"status": "error", "error": safe}, status=400)


@login_required
@permission_required("netbox_unifi_sync.view_sitemapping", raise_exception=True)
def mapping_list_view(request: HttpRequest) -> HttpResponse:
    mappings = SiteMapping.objects.select_related("controller").order_by("controller__name", "unifi_site")
    return render(request, "netbox_unifi_sync/mappings.html", {"mappings": mappings})


@login_required
@permission_required("netbox_unifi_sync.change_sitemapping", raise_exception=True)
def mapping_edit_view(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    mapping = get_object_or_404(SiteMapping, pk=pk) if pk else None
    form = SiteMappingForm(instance=mapping)
    if request.method == "POST":
        form = SiteMappingForm(request.POST, instance=mapping)
        if form.is_valid():
            row = form.save()
            messages.success(request, "Site mapping saved")
            record_event(action="mapping.save", status="success", actor=request.user, target=str(row.pk), message="Site mapping saved")
            return redirect("plugins:netbox_unifi_sync:mappings")
        messages.error(request, "Unable to save mapping. Fix validation errors.")
    return render(request, "netbox_unifi_sync/mapping_form.html", {"form": form, "mapping": mapping})


@login_required
@permission_required("netbox_unifi_sync.delete_sitemapping", raise_exception=True)
def mapping_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    mapping = get_object_or_404(SiteMapping, pk=pk)
    if request.method == "POST":
        mapping.delete()
        messages.success(request, "Site mapping deleted")
        record_event(action="mapping.delete", status="success", actor=request.user, message="Site mapping deleted")
        return redirect("plugins:netbox_unifi_sync:mappings")
    return render(request, "netbox_unifi_sync/mapping_delete.html", {"mapping": mapping})


@login_required
@permission_required("netbox_unifi_sync.view_syncrun", raise_exception=True)
def run_list_view(request: HttpRequest) -> HttpResponse:
    queryset = SyncRun.objects.order_by("-created")
    form = RunFilterForm(request.GET)
    if form.is_valid():
        status = (form.cleaned_data.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        q = (form.cleaned_data.get("q") or "").strip()
        if q:
            queryset = queryset.filter(Q(summary__icontains=q) | Q(error__icontains=q))
        limit = form.cleaned_data.get("limit") or 100
    else:
        limit = 100

    runs = queryset[:limit]
    return render(request, "netbox_unifi_sync/runs.html", {"runs": runs, "form": form, "total": queryset.count()})


@login_required
@permission_required("netbox_unifi_sync.view_syncrun", raise_exception=True)
def run_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    run = get_object_or_404(SyncRun, pk=pk)
    return render(request, "netbox_unifi_sync/run_detail.html", {"run": run})


@login_required
@permission_required("netbox_unifi_sync.view_pluginauditevent", raise_exception=True)
def audit_list_view(request: HttpRequest) -> HttpResponse:
    events = PluginAuditEvent.objects.select_related("actor").order_by("-created")[:200]
    return render(request, "netbox_unifi_sync/audit.html", {"events": events})


@login_required
@permission_required("netbox_unifi_sync.view_syncrun", raise_exception=True)
def api_status_view(request: HttpRequest) -> JsonResponse:
    settings_obj = get_or_create_global_settings()
    latest = SyncRun.objects.order_by("-created").first()
    payload = {
        "enabled": settings_obj.enabled,
        "schedule_enabled": settings_obj.schedule_enabled,
        "sync_interval_minutes": settings_obj.sync_interval_minutes,
        "latest_run": None,
    }
    if latest:
        payload["latest_run"] = {
            "id": latest.pk,
            "status": latest.status,
            "created": latest.created.isoformat(),
            "completed": latest.completed.isoformat() if latest.completed else None,
            "summary": latest.summary,
            "controllers": latest.controllers_total,
            "sites": latest.sites_total,
            "devices": latest.devices_total,
        }
    return JsonResponse(payload)
