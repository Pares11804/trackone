from django.contrib import admin

from apps.metrics.models import MetricIngest, MonitoredHost


@admin.register(MonitoredHost)
class MonitoredHostAdmin(admin.ModelAdmin):
    list_display = ("name", "hostname_hint", "last_seen_at", "created_at")
    readonly_fields = ("api_token_hash", "created_at", "last_seen_at")
    search_fields = ("name", "hostname_hint")


@admin.register(MetricIngest)
class MetricIngestAdmin(admin.ModelAdmin):
    list_display = ("host", "agent_hostname", "collected_at", "received_at")
    list_filter = ("host",)
    readonly_fields = ("host", "agent_hostname", "collected_at", "payload", "received_at")
    ordering = ("-collected_at",)
