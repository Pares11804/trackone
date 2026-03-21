# Deploy TrackOne control host on Oracle Linux (VM)

This guide assumes:

- A VM (example hostname **`nyvm741`**) running **Oracle Linux** (RHEL-compatible).
- You log in as the **`oracle`** OS user (or any user with a home directory and permission to run Python).
- You will use **PostgreSQL** for Django (same as the rest of this project). *Oracle Database is not used unless you change Django settings yourself.*

---

## 1. Connect to the VM

From your workstation:

```bash
ssh oracle@nyvm741
```

If DNS does not resolve, use the VM’s IP:

```bash
ssh oracle@192.168.x.x
```

Use `sudo` for steps that install system packages or change firewall rules. If `oracle` has no sudo, ask your admin to run those parts or grant sudo.

---

## 2. Install system packages

**Python 3** and **PostgreSQL** on the VM (**native** install — same as the main README; no Docker for the database here).

### PostgreSQL on the VM

```bash
sudo dnf install -y python3 python3-pip python3-devel git
sudo dnf install -y postgresql-server postgresql-contrib
```

Initialize and start PostgreSQL (first time only):

```bash
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
```

Create DB user and database (adjust password):

```bash
sudo -u postgres psql -c "CREATE USER trackone WITH PASSWORD 'YOUR_STRONG_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE trackonedb OWNER trackone;"
```

---

## 3. Copy the project onto the VM

**Option 1 — Git (if the VM can reach your Git server):**

```bash
cd ~
git clone <YOUR_TRACKONE_REPO_URL> trackone
cd trackone/control_host
```

**Option 2 — SCP from your PC** (run on your PC, not on the VM):

```bash
scp -r C:\path\to\trackone oracle@nyvm741:~/
```

Then on the VM:

```bash
cd ~/trackone/control_host
```

---

## 4. Python virtual environment and Django

```bash
cd ~/trackone/control_host
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create **`control_host/.env`** (copy from `env.example` and edit):

```env
POSTGRES_DB=trackonedb
POSTGRES_USER=trackone
POSTGRES_PASSWORD=YOUR_STRONG_PASSWORD
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DJANGO_SECRET_KEY=long-random-string-change-me
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,nyvm741,192.168.x.x

# URL you put in trackoneagent config (no trailing slash)
TRACKONE_PUBLIC_BASE_URL=http://192.168.x.x:8000
```

Replace `192.168.x.x` with the VM’s real IP. Include **`nyvm741`** in `DJANGO_ALLOWED_HOSTS` if browsers use that hostname.

Migrate and admin user:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py create_monitored_host web-01
# or: python manage.py build_trackoneagent_bundle web-01 --control-url http://VM_IP:8000
```

---

## 5. Firewall (so other machines can reach the API)

Oracle Linux often uses **firewalld**:

```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

If you use **iptables** only, add an equivalent allow rule for TCP 8000.

**SELinux:** if HTTP fails oddly after the firewall is open, you may need a policy or temporary `setenforce 0` for testing (only on lab systems).

---

## 6. Run the control host

**Development / lab (not for production load):**

```bash
cd ~/trackone/control_host
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

- On the VM: `http://127.0.0.1:8000/`
- From your phone/PC: `http://<VM_IP>:8000/`

**Production-style:** use **Gunicorn** (or uWSGI) + **nginx** or a reverse proxy, with TLS. Example install:

```bash
pip install gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Run Gunicorn under **systemd** so it survives logout and reboots.

---

## 7. Point trackoneagent at this VM

On each client, set:

```env
TRACKONE_CONTROL_URL=http://<VM_IP_OR_nyvm741>:8000
TRACKONE_API_TOKEN=<token from create_monitored_host or bundle>
```

Use the same URL you put in `TRACKONE_PUBLIC_BASE_URL` when building bundles.

---

## Checklist

| Step | Done? |
|------|--------|
| SSH as `oracle@nyvm741` | |
| Python 3 + venv + `pip install -r requirements.txt` | |
| PostgreSQL running + `trackonedb` + `trackone` user | |
| `control_host/.env` with DB + `DJANGO_ALLOWED_HOSTS` + `SECRET_KEY` | |
| `migrate` + `createsuperuser` + monitored host / token | |
| Firewall port **8000** (or 80/443 behind nginx) | |
| `runserver 0.0.0.0:8000` or Gunicorn **0.0.0.0** | |
| Clients use `http://VM:8000` in agent config | |

---

## If something fails

- **Connection refused from another host:** see README *Troubleshooting: refused to connect* — bind `0.0.0.0`, open firewall, use `:8000` in the URL.
- **DisallowedHost:** add the hostname or IP to `DJANGO_ALLOWED_HOSTS`.
- **`oracle` user home:** project can live in `/home/oracle/trackone`; adjust paths if your home differs.

---

## Using Oracle Database instead of PostgreSQL

This repository is set up for **PostgreSQL** only. Moving Django to **Oracle DB** requires changing `DATABASES` in `settings.py`, installing **oracledb** (or **cx_Oracle**), and creating the schema — that is a separate integration project, not covered here.
