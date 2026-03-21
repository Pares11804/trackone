"""Normalize TRACKONE_CONTROL_URL (e.g. duplicate http:// from hand-edited config)."""


def normalize_control_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    # Common mistake: TRACKONE_CONTROL_URL=http://http://host:port/
    lowered = u.lower()
    for _ in range(8):
        if lowered.startswith("http://http://"):
            u = "http://" + u[14:]
        elif lowered.startswith("https://https://"):
            u = "https://" + u[16:]
        elif lowered.startswith("http://https://"):
            u = "https://" + u[13:]
        elif lowered.startswith("https://http://"):
            u = "http://" + u[13:]
        else:
            break
        lowered = u.lower()
    return u
