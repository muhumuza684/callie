"""Tiny JSON store: contacts, recents (call log) and scheduled calls. Single user, local."""
import copy
import json
import re
import secrets
from datetime import datetime
from pathlib import Path

from server import config

PATH = config.HOME / "data" / "store.json"
VOICES = ("female", "male", "girl", "boy", "baby", "adult", "old_lady", "old_man", "stranger")
LEGACY = {"lady": "female", "man": "male"}
DEFAULT = {
    "contacts": [
        {"id": "callie", "name": "Callie", "voice": "female", "color": 0},
        {"id": "mary", "name": "Mary", "voice": "female", "color": 1},
        {"id": "john", "name": "John", "voice": "male", "color": 2},
        {"id": "amara", "name": "Amara", "voice": "girl", "color": 3},
    ],
    "recents": [],
    "schedule": [],
    "settings": {"memory": False},
}


def load() -> dict:
    d = copy.deepcopy(DEFAULT)
    if PATH and PATH.exists():
        try:
            d = json.loads(PATH.read_text())
        except Exception:
            pass
    for c in d["contacts"]:
        c["voice"] = LEGACY.get(c["voice"], c["voice"])      # older saves used lady/man
        c.setdefault("lang", "en")
    d.setdefault("settings", {}).setdefault("memory", False)
    return d


def save(d: dict):
    if PATH:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(d))


def contact(cid: str | None):
    d = load()
    return next((c for c in d["contacts"] if c["id"] == cid), d["contacts"][0] if d["contacts"] else None)


def add_contact(name: str, voice: str, lang: str = "en") -> dict:
    d = load()
    c = {"id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + "-" + secrets.token_hex(2),
         "name": name.strip()[:16], "voice": voice, "lang": lang, "color": len(d["contacts"]) % 6}
    d["contacts"].append(c)
    save(d)
    return c


def add_recent(cid: str, seconds: int):
    d = load()
    d["recents"] = ([{"contact": cid, "at": datetime.now().isoformat(timespec="seconds"), "seconds": seconds}]
                    + d["recents"])[:30]
    save(d)
