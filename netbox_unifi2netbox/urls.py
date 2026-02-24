from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = (
    path("", views.status_view, name="status"),
    path("runs/", views.syncrun_list_view, name="syncrun_list"),
    path("runs/<int:pk>/", views.syncrun_detail_view, name="syncrun_detail"),
)
