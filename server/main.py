"""Voice AI server. NOTE: static mount MUST come after API/WebSocket routes,
otherwise the "/" mount swallows /health and /ws/voice."""
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from server import config, memory, store
from server.ws import handle_voice_socket

PWA_DIR = config.RESOURCE_DIR / "client" / "pwa"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voice-ai")

# technical details go to a file only the owners read
LOG_DIR = config.HOME / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_fh = RotatingFileHandler(LOG_DIR / "callie.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.getLogger().addHandler(_fh)

# no public API documentation: the inside of the system is not advertised
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(RequestValidationError)
async def _invalid(request, exc):
    return JSONResponse({"error": "invalid"}, status_code=400)


@app.exception_handler(Exception)
async def _unavailable(request, exc):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse({"error": "unavailable"}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok"}


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=16)
    voice: Literal["female", "male", "girl", "boy", "baby", "adult", "old_lady", "old_man", "stranger"]
    lang: Literal["en", "sw", "fr", "es", "ar", "zh", "hi", "pt"] = "en"


class ScheduleIn(BaseModel):
    contact: str
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


@app.get("/api/state")
async def state():
    return {**store.load(), "types": [{"id": k, "label": v["label"]} for k, v in config.TYPES.items()],
            "langs": [{"id": k, "label": v["native"]} for k, v in config.LANGS.items()],
            "support": config.SUPPORT_EMAILS, "version": config.VERSION}


@app.post("/api/contacts")
async def new_contact(c: ContactIn):
    return store.add_contact(c.name, c.voice, c.lang)


@app.delete("/api/contacts/{cid}")
async def del_contact(cid: str):
    d = store.load()
    if len(d["contacts"]) <= 1:
        raise HTTPException(409, "keep at least one contact")
    d["contacts"] = [c for c in d["contacts"] if c["id"] != cid]
    d["schedule"] = [x for x in d["schedule"] if x["contact"] != cid]
    store.save(d)
    memory.clear(cid)
    return {"ok": True}


class SettingsIn(BaseModel):
    memory: bool


@app.post("/api/settings")
async def set_settings(s: SettingsIn):
    d = store.load()
    d["settings"]["memory"] = s.memory
    store.save(d)
    return d["settings"]


@app.delete("/api/memory")
async def clear_memory():
    memory.clear()
    return {"ok": True}


@app.post("/api/schedule")
async def new_schedule(s: ScheduleIn):
    d = store.load()
    item = {"id": store.secrets.token_hex(3), "contact": s.contact, "time": s.time, "on": True}
    d["schedule"].append(item)
    store.save(d)
    return item


@app.post("/api/schedule/{sid}/toggle")
async def toggle_schedule(sid: str):
    d = store.load()
    for x in d["schedule"]:
        if x["id"] == sid:
            x["on"] = not x["on"]
    store.save(d)
    return {"ok": True}


@app.delete("/api/schedule/{sid}")
async def del_schedule(sid: str):
    d = store.load()
    d["schedule"] = [x for x in d["schedule"] if x["id"] != sid]
    store.save(d)
    return {"ok": True}


STATE = {"ping": 0.0}


@app.api_route("/api/ping", methods=["GET", "POST"])
async def ping():
    STATE["ping"] = time.monotonic()      # the desktop app closes itself when its window stops pinging
    return {"ok": True}


class SetupIn(BaseModel):
    key: str = Field(min_length=20, max_length=200, pattern=r"^gsk_[A-Za-z0-9_\-]+$")


def _write_env_key(key: str):
    lines = config.ENV_PATH.read_text().splitlines() if config.ENV_PATH.exists() else []
    lines = [ln for ln in lines if not ln.startswith("GROQ_API_KEY=")] + [f"GROQ_API_KEY={key}"]
    config.ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.ENV_PATH.write_text("\n".join(lines) + "\n")


@app.get("/setup")
async def setup_page():
    return FileResponse(PWA_DIR / "setup.html")


@app.post("/api/setup")
async def setup(body: SetupIn, request: Request):
    """First run only, from this computer only (never through a shared link): saves the access key."""
    shared = any(h in request.headers for h in ("x-forwarded-for", "cf-connecting-ip", "forwarded"))
    local = request.client is not None and request.client.host in ("127.0.0.1", "::1", "testclient")
    if config.GROQ_API_KEY or shared or not local:
        raise HTTPException(403, "closed")
    _write_env_key(body.key)
    config.GROQ_API_KEY = body.key
    os.environ["GROQ_API_KEY"] = body.key
    return {"ok": True}


@app.websocket("/ws/voice")
async def voice_socket(ws: WebSocket):
    try:
        await handle_voice_socket(ws)
    except WebSocketDisconnect:
        log.info("client disconnected")


class NoCacheStatic(StaticFiles):
    """Always revalidate, so a new version never shows up half-styled from the browser cache."""

    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers["Cache-Control"] = "no-cache"
        return r


app.mount("/", NoCacheStatic(directory=PWA_DIR, html=True), name="pwa")
