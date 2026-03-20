import secrets
import shutil
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.metrics.models import MonitoredHost, hash_api_token


def _repo_root() -> Path:
    # trackone/control_host/apps/metrics/management/commands/this.py -> parents[5] == trackone
    return Path(__file__).resolve().parents[5]


class Command(BaseCommand):
    help = (
        "Create MonitoredHost + a ready-to-copy folder trackoneagent_<name>/ with code and pre-filled config.env."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "name",
            type=str,
            help="Unique host slug (e.g. web-01). Must not already exist in the database.",
        )
        parser.add_argument(
            "--control-url",
            dest="control_url",
            default="",
            help="Base URL clients use to reach this control host, e.g. http://192.168.1.10:8000 "
            "(no trailing slash). Overrides TRACKONE_PUBLIC_BASE_URL from .env.",
        )
        parser.add_argument(
            "--hostname-hint",
            default="",
            dest="hint",
            help="Optional note stored on MonitoredHost (not used for auth).",
        )
        parser.add_argument(
            "--interval",
            default="30",
            help="TRACKONE_INTERVAL_SECONDS written into config.env (default 30).",
        )
        parser.add_argument(
            "--out",
            type=Path,
            default=None,
            help="Output directory for the bundle folder (default: AGENT_BUNDLE_DIR from settings).",
        )
        parser.add_argument(
            "--zip",
            action="store_true",
            help="Also create trackoneagent_<name>.zip next to the bundle folder.",
        )

    def handle(self, *args, **options) -> None:
        name = options["name"].strip()
        if not name:
            raise CommandError("name must not be empty")

        control_url = (options.get("control_url") or "").strip().rstrip("/")
        if not control_url:
            control_url = getattr(settings, "TRACKONE_PUBLIC_BASE_URL", "").strip().rstrip("/")
        if not control_url:
            raise CommandError(
                "Set control URL: pass --control-url https://monitoring.example.com "
                "or set TRACKONE_PUBLIC_BASE_URL in control_host/.env"
            )

        if MonitoredHost.objects.filter(name=name).exists():
            raise CommandError(
                f'MonitoredHost "{name}" already exists. '
                "Use a new slug, or delete the host in admin. "
                "(Plaintext tokens are not stored, so existing hosts cannot be re-bundled automatically.)"
            )

        raw_token = secrets.token_urlsafe(32)
        MonitoredHost.objects.create(
            name=name,
            hostname_hint=options.get("hint") or "",
            api_token_hash=hash_api_token(raw_token),
        )

        bundle_parent = Path(options["out"]) if options.get("out") else Path(settings.AGENT_BUNDLE_DIR)
        bundle_parent.mkdir(parents=True, exist_ok=True)
        out_dir = bundle_parent / f"trackoneagent_{name}"

        if out_dir.exists():
            shutil.rmtree(out_dir)

        repo = _repo_root()
        sys.path.insert(0, str(repo))
        try:
            from packaging.bundle_builder import build_portable_bundle

            build_portable_bundle(out_dir, repo)
        except Exception as e:
            MonitoredHost.objects.filter(name=name).delete()
            raise CommandError(f"Bundle build failed: {e}") from e

        config_body = "\n".join(
            [
                f"TRACKONE_CONTROL_URL={control_url}",
                f"TRACKONE_API_TOKEN={raw_token}",
                f"TRACKONE_INTERVAL_SECONDS={options.get('interval') or '30'}",
                "",
                "# Built by: python manage.py build_trackoneagent_bundle",
                "# Keep this folder private - it contains your API token.",
            ]
        )
        (out_dir / "config.env").write_text(config_body, encoding="utf-8")

        (out_dir / "BUNDLE_INFO.txt").write_text(
            "\n".join(
                [
                    f"MonitoredHost name: {name}",
                    f"Control URL: {control_url}",
                    "",
                    "On the client: copy this entire folder, run setup_windows.bat or setup_linux.sh once,",
                    "then start_agent_background.bat / start_agent_background.sh (or python -m trackoneagent).",
                    "",
                    "Python is still required on the client unless you use a frozen executable; see README.",
                ]
            ),
            encoding="utf-8",
        )

        self.stdout.write(self.style.SUCCESS(f"Created MonitoredHost {name!r} and bundle:\n  {out_dir}"))

        if options.get("zip"):
            archive_base = bundle_parent / f"trackoneagent_{name}"
            shutil.make_archive(str(archive_base), "zip", root_dir=str(bundle_parent), base_dir=f"trackoneagent_{name}")
            self.stdout.write(self.style.SUCCESS(f"Zip: {archive_base}.zip"))

        self.stdout.write(
            self.style.WARNING(
                "The API token exists only in config.env inside that folder (and as a hash in the DB). "
                "Do not publish the bundle."
            )
        )
