"""Fair use in hosted mode: one call per person at a time, a daily call-time allowance, and a cap on calls at once."""
import json
import re
import secrets
from datetime import date

from server import auth, config

_active: set = set()
_minutes: dict = {}


def can_start(uid) -> str | None:
    """None = go ahead, otherwise the notice code to show."""
    if not config.HOSTED or uid is None:
        return None
    if uid in _active or len(_active) >= config.MAX_CONCURRENT_CALLS:
        return "busy"
    if _minutes.get((uid, date.today()), 0.0) >= config.LIMIT_MINUTES_PER_DAY:
        return "limit"
    return None


def start(uid):
    if uid is not None:
        _active.add(uid)


def end(uid, seconds: float):
    if uid is None:
        return
    _active.discard(uid)
    today = date.today()
    _minutes[(uid, today)] = _minutes.get((uid, today), 0.0) + seconds / 60
    for k in [k for k in _minutes if k[1] != today]:      # forget old days
        del _minutes[k]


# ---- calls per device per day -------------------------------------------------------------------------
# A "device" is a browser that holds a signed device cookie (set the first time it opens Callie). A browser
# without one is counted by its address instead, so clearing cookies does not give a fresh allowance.
# The counts are kept in a small file, so they survive the app closing and restarting.
DEVICE_COOKIE = "callie_device"
_PROXY_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "x-real-ip")


def is_remote(headers) -> bool:
    """True when the request came through a link (tunnel or server), False for the computer itself."""
    return config.HOSTED or any(headers.get(h) for h in _PROXY_HEADERS)


def _address(headers, client_host) -> str:
    raw = headers.get("cf-connecting-ip") or (headers.get("x-forwarded-for") or "").split(",")[0] or headers.get("x-real-ip") or client_host or "?"
    return re.sub(r"[^0-9A-Za-z:.]", "", raw.strip())[:45] or "?"


def new_device_cookie() -> str:
    return auth.sign(secrets.token_hex(8))


def device_key(cookies, headers, client_host) -> str:
    dev = auth.verify(cookies.get(DEVICE_COOKIE))
    return f"d:{dev}" if dev else f"a:{_address(headers, client_host)}"


def _usage_file():
    return config.HOME / "usage.json"


def _load() -> dict:
    today = date.today().isoformat()
    try:
        d = json.loads(_usage_file().read_text())
    except Exception:
        d = {}
    if not isinstance(d, dict) or d.get("day") != today or not isinstance(d.get("n"), dict):
        d = {"day": today, "n": {}}
    return d


def _save(d: dict):
    try:
        f = _usage_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        tmp.replace(f)
    except Exception:
        pass                                  # never let counting break a call


def device_can_start(key: str) -> str | None:
    """None = go ahead, "daily" = this device has used today's calls."""
    if config.CALLS_PER_DEVICE_PER_DAY <= 0:
        return None
    return "daily" if _load()["n"].get(key, 0) >= config.CALLS_PER_DEVICE_PER_DAY else None


def device_count(key: str, delta: int):
    d = _load()
    d["n"][key] = max(0, d["n"].get(key, 0) + delta)
    _save(d)
