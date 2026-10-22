"""Hosted mode: invite-code sign-in, a signed cookie, and a separate data folder for every person.
On a personal computer (the default) none of this is active."""
import hashlib
import hmac
import re
import secrets
import shutil
from contextvars import ContextVar
from datetime import datetime, timezone

from server import config

COOKIE = "callie_session"
USER: ContextVar = ContextVar("callie_user", default=None)     # who the current request or call belongs to
_UID = re.compile(r"^[a-f0-9]{16}$")


def _secret() -> bytes:
    if config.SESSION_SECRET:
        return config.SESSION_SECRET.encode()
    f = config.HOME / "session.key"                              # created once, so sign-ins survive restarts
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip().encode()


def _mac(uid: str) -> str:
    return hmac.new(_secret(), uid.encode(), hashlib.sha256).hexdigest()[:32]


def sign(uid: str) -> str:
    return f"{uid}.{_mac(uid)}"


def verify(token: str | None):
    if not token or "." not in token:
        return None
    uid, mac = token.split(".", 1)
    return uid if _UID.match(uid) and hmac.compare_digest(mac, _mac(uid)) else None


def identify(cookies) -> tuple:
    """(allowed, user id). Not hosted: always allowed, no user id (the normal single-user folders are used)."""
    if not config.HOSTED:
        return True, None
    uid = verify(cookies.get(COOKIE))
    return uid is not None, uid


def check_code(code: str) -> bool:
    return any(hmac.compare_digest(code.strip(), c) for c in config.INVITE_CODES)


def user_dir(uid: str):
    return config.HOME / "users" / uid


def new_user() -> str:
    uid = secrets.token_hex(8)
    d = user_dir(uid)
    (d / "data").mkdir(parents=True, exist_ok=True)
    (d / "consent.json").write_text('{"agreed": "%s", "version": 1}' % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return uid


def delete_user(uid: str):
    if _UID.match(uid):
        shutil.rmtree(user_dir(uid), ignore_errors=True)
