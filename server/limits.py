"""Fair use in hosted mode: one call per person at a time, a daily call-time allowance, and a cap on calls at once."""
from datetime import date

from server import config

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
