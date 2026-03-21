from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.metrics.bytes_format import format_bytes_df_h
from apps.metrics.models import MonitoredHost, MetricIngest, hash_api_token
from apps.metrics.series import downsample, extract_chart_point


def _disk_df_rows_from_latest_ingest(ing: MetricIngest | None) -> tuple[list[dict[str, Any]], Any]:
    """Build df -h style rows from the latest stored ingest (backward compatible)."""
    if ing is None:
        return [], None
    payload = ing.payload if isinstance(ing.payload, dict) else {}
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    disk = metrics.get("disk") if isinstance(metrics.get("disk"), dict) else {}
    parts = disk.get("partitions")
    if not isinstance(parts, list):
        return [], ing.collected_at
    rows: list[dict[str, Any]] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        tb, ub, fb = p.get("total_bytes"), p.get("used_bytes"), p.get("free_bytes")
        pct = p.get("percent")
        use_str = p.get("use_pcent")
        if not use_str and pct is not None:
            try:
                use_str = f"{float(pct):.0f}%"
            except (TypeError, ValueError):
                use_str = "—"
        elif not use_str:
            use_str = "—"
        rows.append(
            {
                "device": str(p.get("device", "")),
                "fstype": str(p.get("fstype", "")),
                "mountpoint": str(p.get("mountpoint", "")),
                "size_h": p.get("size_h") or format_bytes_df_h(tb),
                "used_h": p.get("used_h") or format_bytes_df_h(ub),
                "avail_h": p.get("avail_h") or format_bytes_df_h(fb),
                "use_pcent": use_str,
            }
        )
    return rows, ing.collected_at


@require_GET
def home(request: HttpRequest):
    return render(request, "metrics/home.html")


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def _authenticate_host(request: HttpRequest) -> MonitoredHost | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    raw = auth[7:].strip()
    if not raw:
        return None
    digest = hash_api_token(raw)
    try:
        return MonitoredHost.objects.get(api_token_hash=digest)
    except MonitoredHost.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def ingest_metrics(request: HttpRequest) -> JsonResponse:
    host = _authenticate_host(request)
    if host is None:
        return _json_error("Unauthorized", status=401)

    try:
        body: dict[str, Any] = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error("Invalid JSON body")

    agent_hostname = body.get("hostname")
    if not agent_hostname or not isinstance(agent_hostname, str):
        return _json_error("Missing or invalid 'hostname'")
    ts = body.get("timestamp")
    if not ts or not isinstance(ts, str):
        return _json_error("Missing or invalid 'timestamp' (ISO-8601 string)")
    collected_at = parse_datetime(ts)
    if collected_at is None:
        return _json_error("Could not parse 'timestamp'")
    if timezone.is_naive(collected_at):
        collected_at = timezone.make_aware(collected_at, timezone.get_current_timezone())

    metrics = body.get("metrics")
    if not isinstance(metrics, dict):
        return _json_error("Missing or invalid 'metrics' object")

    payload = {
        "hostname": agent_hostname,
        "metrics": metrics,
    }

    row = MetricIngest.objects.create(
        host=host,
        agent_hostname=agent_hostname[:255],
        collected_at=collected_at,
        payload=payload,
    )
    MonitoredHost.objects.filter(pk=host.pk).update(last_seen_at=timezone.now())

    return JsonResponse({"ok": True, "ingest_id": row.pk})


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True, "service": "trackone-control"})


def _parse_range_aware(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    dt = parse_datetime(raw)
    if dt is None:
        return default
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@login_required
@require_GET
def metrics_dashboard(request: HttpRequest):
    hosts = MonitoredHost.objects.order_by("name")
    default_host = hosts.first()
    host_param = request.GET.get("host")
    selected_id = None
    if host_param and host_param.isdigit():
        cand = int(host_param)
        if hosts.filter(pk=cand).exists():
            selected_id = cand
    if selected_id is None and default_host is not None:
        selected_id = default_host.pk
    selected_host = None
    if selected_id is not None:
        selected_host = hosts.filter(pk=selected_id).first()
    latest_ingest = None
    if selected_host is not None:
        latest_ingest = (
            MetricIngest.objects.filter(host=selected_host)
            .order_by("-collected_at")
            .only("payload", "collected_at")
            .first()
        )
    disk_df_rows, disk_snapshot_at = _disk_df_rows_from_latest_ingest(latest_ingest)
    return render(
        request,
        "metrics/dashboard.html",
        {
            "hosts": hosts,
            "selected_host_id": selected_id,
            "selected_host": selected_host,
            "disk_df_rows": disk_df_rows,
            "disk_snapshot_at": disk_snapshot_at,
        },
    )


@login_required
@require_GET
def dashboard_series(request: HttpRequest) -> JsonResponse:
    host_param = request.GET.get("host")
    if not host_param or not host_param.isdigit():
        return _json_error("Missing or invalid 'host' id", status=400)
    host = get_object_or_404(MonitoredHost, pk=int(host_param))

    now = timezone.now()
    to_dt = _parse_range_aware(request.GET.get("to"), now)
    from_dt = _parse_range_aware(request.GET.get("from"), to_dt - timedelta(hours=24))
    if from_dt >= to_dt:
        return _json_error("'from' must be before 'to'", status=400)

    qs = (
        MetricIngest.objects.filter(
            host=host,
            collected_at__gte=from_dt,
            collected_at__lte=to_dt,
        )
        .order_by("collected_at")
        .only("payload", "collected_at")[:8000]
    )

    points: list[dict[str, Any]] = []
    for row in qs:
        if not isinstance(row.payload, dict):
            continue
        points.append(extract_chart_point(row.payload, row.collected_at))

    points = downsample(points, max_points=2500)

    return JsonResponse(
        {
            "ok": True,
            "host_id": host.pk,
            "host_name": host.name,
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
            "points": points,
        }
    )
