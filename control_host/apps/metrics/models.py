from __future__ import annotations

import hashlib

from django.db import models


def hash_api_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MonitoredHost(models.Model):
    """A client host that the agent runs on; authenticated via API token (hashed)."""

    name = models.SlugField(max_length=128, unique=True, help_text="Logical name, e.g. web-01")
    hostname_hint = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional note; agent reports actual hostname in payloads.",
    )
    # Unique index: every ingest authenticates with a hash lookup; keeps latency flat as host count grows.
    api_token_hash = models.CharField(max_length=64, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MetricIngest(models.Model):
    """One agent push: CPU / memory / disk (and future) in JSON."""

    host = models.ForeignKey(
        MonitoredHost,
        on_delete=models.CASCADE,
        related_name="ingests",
    )
    agent_hostname = models.CharField(max_length=255)
    collected_at = models.DateTimeField(db_index=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-collected_at"]
        indexes = [
            models.Index(fields=["host", "-collected_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.host.name} @ {self.collected_at}"
