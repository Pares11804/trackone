from django.urls import path

from apps.metrics import views

urlpatterns = [
    path("v1/ingest/", views.ingest_metrics, name="metrics-ingest"),
    path("v1/health/", views.health, name="metrics-health"),
]
