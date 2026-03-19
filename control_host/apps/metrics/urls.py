from django.urls import path

from apps.metrics import views

urlpatterns = [
    path("metrics/dashboard/", views.metrics_dashboard, name="metrics-dashboard"),
    path("metrics/api/series/", views.dashboard_series, name="metrics-dashboard-series"),
]
