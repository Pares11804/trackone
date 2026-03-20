import secrets

from django.core.management.base import BaseCommand

from apps.metrics.models import MonitoredHost, hash_api_token


class Command(BaseCommand):
    help = "Register a monitored host and print a one-time API token for trackoneagent."

    def add_arguments(self, parser) -> None:
        parser.add_argument("name", type=str, help="Unique slug, e.g. web-01")
        parser.add_argument(
            "--hostname-hint",
            default="",
            dest="hint",
            help="Optional label shown in admin (not used for auth).",
        )

    def handle(self, *args, **options) -> None:
        name = options["name"]
        hint = options["hint"] or ""
        if MonitoredHost.objects.filter(name=name).exists():
            self.stderr.write(self.style.ERROR(f'Host "{name}" already exists.'))
            return

        raw = secrets.token_urlsafe(32)
        MonitoredHost.objects.create(
            name=name,
            hostname_hint=hint,
            api_token_hash=hash_api_token(raw),
        )
        self.stdout.write(self.style.SUCCESS(f'Created monitored host "{name}".'))
        self.stdout.write("Configure trackoneagent with this token (shown once):\n")
        self.stdout.write(raw)
