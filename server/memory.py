"""Optional conversation memory (off by default). A short summary plus the last few messages per contact,
stored only on this computer in data/memory.json."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "memory.json"
MAX_RECENT = 20


def _load() -> dict:
    if PATH and PATH.exists():
        try:
            return json.loads(PATH.read_text())
        except Exception:
            pass
    return {}


def _save(d: dict):
    if PATH:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(d))


def get(cid: str) -> dict:
    return _load().get(cid, {"summary": "", "recent": []})


def put(cid: str, summary: str, recent: list):
    d = _load()
    d[cid] = {"summary": summary[:800], "recent": recent[-MAX_RECENT:]}
    _save(d)


def clear(cid: str | None = None):
    d = {} if cid is None else _load()
    d.pop(cid, None)
    _save(d)
