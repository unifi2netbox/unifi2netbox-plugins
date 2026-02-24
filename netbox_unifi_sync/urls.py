from __future__ import annotations

from django.urls import path

from . import views

app_name = "netbox_unifi_sync"

urlpatterns = (
    path("", views.dashboard_view, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("controllers/", views.controller_list_view, name="controllers"),
    path("controllers/add/", views.controller_edit_view, name="controller_add"),
    path("controllers/<int:pk>/edit/", views.controller_edit_view, name="controller_edit"),
    path("controllers/<int:pk>/delete/", views.controller_delete_view, name="controller_delete"),
    path("controllers/<int:pk>/test/", views.controller_test_view, name="controller_test"),

    path("mappings/", views.mapping_list_view, name="mappings"),
    path("mappings/add/", views.mapping_edit_view, name="mapping_add"),
    path("mappings/<int:pk>/edit/", views.mapping_edit_view, name="mapping_edit"),
    path("mappings/<int:pk>/delete/", views.mapping_delete_view, name="mapping_delete"),

    path("runs/", views.run_list_view, name="runs"),
    path("runs/<int:pk>/", views.run_detail_view, name="run_detail"),
    path("audit/", views.audit_list_view, name="audit"),
)
