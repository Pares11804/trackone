# TrackOne — control host + agent monitoring

Small monitoring stack: a **control host** (Django + PostgreSQL on Linux) receives periodic metric pushes from an **agent** on client machines (Windows or Linux). Version one collects **CPU**, **memory**, and **disk** via shared modules under `monitoring_scripts/`.

## Plain-language guide (if you’re new to this)

**The story in one picture:** You have **one main computer** (the *control host*) that keeps a database of “how are my machines doing?” Each **client computer** runs a tiny background program called the **agent**. Every X seconds the agent measures CPU, RAM, and disks on *that* machine and sends the numbers over the network to the control host. So one server can watch many clients.

**What is Docker (here)?** Normally you’d *install* PostgreSQL (the database) on the Linux server and configure it yourself. **Docker** is a way to run software in a **container**—think of it like a pre-packed box that already contains PostgreSQL, so you start it with one command instead of a long manual install. The file `docker-compose.yml` in this repo describes a **database box** named `db`. The command `docker compose up -d db` means: “download/start that box in the background (`-d`), and expose Postgres on a port so Django can connect.” You still need **Docker Desktop** (on Windows/Mac) or Docker Engine (on Linux) installed *on the machine where you run that command*—often the same machine that runs the control host.

**Parts of this repo:**

| Idea | Simple meaning |
|------|----------------|
| `control_host/` | The **server app**: web API + admin website + talks to Postgres |
| `agent/` | The **client program** you run on each machine you want to monitor |
| `monitoring_scripts/` | Shared **measuring tools** (CPU/RAM/disk) the agent calls |

**What the client machine needs installed** is spelled out in [Agent — what to install on the client](#agent--what-to-install-on-the-client) below.

## Layout

| Path | Role |
|------|------|
| `monitoring_scripts/` | Collectors (`cpu`, `memory`, `disk`) used by the agent |
| `control_host/` | Django project: REST-style ingest API + admin + Postgres storage |
| `agent/` | Long-running client that samples on an interval and POSTs JSON |

## Scale (dozens of clients on one control host)

**Yes.** The model is agent-initiated HTTP POSTs on an interval (e.g. every 30s). Tens of hosts means on the order of tens of requests per interval spread over time—trivial for Django + PostgreSQL. Roughly: \(N\) hosts × (3600 / interval_seconds) ingests per hour; example: 50 hosts @ 30s ≈ 6k rows/hour into `MetricIngest`, which Postgres handles easily with the existing indexes.

**Production:** Use a real WSGI/ASGI server (e.g. Gunicorn/Uvicorn) behind a reverse proxy, not `runserver`. Over long periods, plan **retention** (prune or archive old `MetricIngest` rows) so the table does not grow without bound.

## Control host (Linux or Windows)

The control host is standard Django + PostgreSQL; **Windows works** the same way as Linux for development and many deployments. Install PostgreSQL natively or run `docker compose up -d db` with **Docker Desktop**. Use a Windows venv (`python -m venv .venv` then `.\.venv\Scripts\Activate.ps1`). For production on Windows, use a Windows-friendly app server (e.g. **Waitress**) or run the app under **WSL2** if you prefer Linux-style Gunicorn/nginx.

1. **PostgreSQL** — use your own server or Docker:

   ```bash
   docker compose up -d db
   ```

2. **Configure** — set env vars (or export in shell):

   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
   - `DJANGO_SECRET_KEY` (production)
   - `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=your.host`

3. **Install and migrate**

   ```bash
   cd control_host
   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py create_monitored_host web-01
   ```

   Copy the printed token for the agent.

4. **Run**

   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

   - Health: `GET /api/v1/health/`
   - Ingest: `POST /api/v1/ingest/` with `Authorization: Bearer <token>`
   - **Charts / history:** `GET /metrics/dashboard/` — line charts (CPU %, memory %, disk % over time). Sign in with your **Django admin** user (same account as `/admin/`). Pick a host, time range, or presets (1 h / 6 h / 24 h / 7 d). Data is read from stored ingests (`collected_at` on the horizontal axis).

   Optional JSON for integrations (also requires an authenticated browser session or future API key):

   `GET /metrics/api/series/?host=<id>&from=<ISO8601>&to=<ISO8601>`

## Agent (Windows or Linux)

### Agent — what to install on the client

The **client does not** need Docker, PostgreSQL, or Django. It only needs:

1. **Python 3** (3.10+ is fine)—from [python.org](https://www.python.org/downloads/) or your OS package manager. During setup on Windows, check *“Add Python to PATH”* so `python` works in the terminal.
2. **This repository** on the client (or at least the folders `agent/` and `monitoring_scripts/` with the same parent folder layout), because the agent imports `monitoring_scripts`.
3. **Python packages** listed in `agent/requirements.txt`:
   - **`psutil`** — reads CPU, memory, disk from the OS (works on Windows and Linux).
   - **`requests`** — sends HTTP POST to your control host.
4. **Network** from the client to the control host: the URL you put in config must be reachable (correct hostname/IP, firewall allows the port, HTTPS if you use TLS).
5. **A valid API token** created on the control host (`python manage.py create_monitored_host some-name`). That long random string is the client’s password.

**Optional but recommended:** a **virtual environment** (`python -m venv .venv`) so you don’t mix TrackOne’s libraries with other Python projects.

### Example: Windows client

1. Install Python 3.x from python.org (add to PATH).
2. Put the project on the machine, e.g. `C:\trackone`.
3. Open PowerShell:

   ```powershell
   cd C:\trackone
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r agent\requirements.txt
   ```

4. Copy `agent\config.example.env` to `agent\config.env`.
5. Edit `agent\config.env`, for example:

   ```env
   TRACKONE_CONTROL_URL=http://192.168.1.50:8000
   TRACKONE_API_TOKEN=paste_the_token_from_create_monitored_host
   TRACKONE_INTERVAL_SECONDS=30
   ```

   Use the real IP or DNS name of your Linux control host and the port your API listens on.

6. From `C:\trackone`, run: `python -m agent`. Leave the window open (or run it as a Windows Service / Scheduled Task later).

7. On the control host, open Django admin—you should see **Metric ingests** and **last_seen_at** updating.

### Example: Linux client

Same idea: `cd /path/to/trackone`, `python -m venv .venv`, `source .venv/bin/activate`, `pip install -r agent/requirements.txt`, configure `agent/config.env`, run `python -m agent`.

---

Install deps from **repository root** so `monitoring_scripts` is importable:

```bash
cd /path/to/trackone
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
cp agent/config.example.env agent/config.env
# Edit agent/config.env: TRACKONE_CONTROL_URL, TRACKONE_API_TOKEN, interval
python -m agent
```

The agent reads `agent/config.env` if present (optional `KEY=value` lines). You can instead set the same variables in the process environment.

### Payload technical shape (optional)

Each POST body:

```json
{
  "hostname": "client-hostname",
  "timestamp": "2026-03-19T12:00:00.000000Z",
  "metrics": {
    "cpu": { "percent": 12.3, ... },
    "memory": { "virtual": { ... }, "swap": { ... } },
    "disk": { "partitions": [ ... ] }
  }
}
```

Rows appear in Django admin as **Metric ingests**; **Monitored hosts** shows `last_seen_at` after each successful push.

## Adding more metrics later

Add a new module under `monitoring_scripts/` (e.g. `network.py` with `collect_network()`), export it from `monitoring_scripts/__init__.py`, and extend `collect_payload()` in `agent/main.py`. The control host stores the full `metrics` object as JSON, so no schema migration is required for new keys.
