# Install Python 3.11 for trackoneagent (client: Windows & Oracle Linux)

TrackOne needs **Python 3.10 or newer**. These steps target **3.11** explicitly. Use them on **client** machines where you run **trackoneagent** (non-Docker).

---

## Windows

### Option A — Official installer (recommended)

1. Open **[Python 3.11 downloads](https://www.python.org/downloads/release/python-3119/)** (or the latest **3.11.x** “Windows installer (64-bit)”).
2. Run the installer.
3. Enable **“Add python.exe to PATH”** at the bottom of the first screen.
4. Choose **Customize** if you want to change the install path; otherwise **Install Now**.
5. Close the installer and **open a new** PowerShell or Command Prompt.

**Verify:**

```powershell
python --version
```

You should see `Python 3.11.x`. If `python` is not found, try `py -3.11`:

```powershell
py -3.11 --version
```

Use that same launcher for the venv:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Option B — winget

```powershell
winget install Python.Python.3.11
```

Sign out/in or open a new terminal, then `python --version`.

---

## Oracle Linux (OEL) — client

### Oracle Linux 9 (9.2 and later)

Python **3.11** is in the **AppStream** repository.

```bash
sudo dnf install -y python3.11 python3.11-pip python3.11-devel
```

- **`python3.11-devel`** helps if `pip` needs to compile wheels (e.g. some `psutil` builds).
- Default `python3` on OL9 may still be **3.9**; always call **3.11** explicitly for the agent.

**Verify:**

```bash
python3.11 --version
python3.11 -m pip --version
```

**Create the venv for trackoneagent** (from your bundle root):

```bash
cd ~/trackone
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r trackoneagent/requirements.txt
```

After `activate`, `python` inside the venv is 3.11.

### Oracle Linux 8

Check if 3.11 exists in your repos:

```bash
dnf search python3.11
```

- If **`python3.11`** appears, install it the same way as OL9 (`sudo dnf install python3.11 python3.11-pip python3.11-devel`).
- If it **does not** appear, either:
  - Use another supported Python **≥ 3.10** from Oracle’s repos (e.g. module `python39` / `python3.9` if that is the newest available — TrackOne works with **3.10+**), or  
  - Install 3.11 from **[Oracle Linux Python](https://yum.oracle.com/oracle-linux-python.html)** / your org’s standard method, or build from source (advanced).

### `pip` / SSL / “externally managed environment”

If `pip install` complains about system packages, use a **venv** (as above). On some systems:

```bash
python3.11 -m ensurepip --upgrade
```

---

## After Python is ready

Continue with the main README: **[Non-Docker: install and verify trackoneagent (step by step)](../README.md#non-docker-install-and-verify-trackoneagent-step-by-step)** (Steps 2–7).

---

## Quick reference

| OS | Install command / action | Run / venv |
|----|---------------------------|------------|
| **Windows** | python.org 3.11 installer + **Add to PATH** | `python -m venv .venv` or `py -3.11 -m venv .venv` |
| **Oracle Linux 9** | `sudo dnf install python3.11 python3.11-pip python3.11-devel` | `python3.11 -m venv .venv` |
| **Oracle Linux 8** | `dnf search python3.11` or use **3.10+** from repos | `python3.X -m venv .venv` |
