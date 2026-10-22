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

from server import auth, config, memory, store
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
    lang: Literal["en", "sw", "lg", "fr", "es", "de", "ar", "zh", "hi", "pt"] = "en"


class ScheduleIn(BaseModel):
    contact: str
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


@app.get("/api/state")
async def state():
    return {**store.load(), "types": [{"id": k, "label": v["label"]} for k, v in config.TYPES.items()],
            "langs": [{"id": k, "label": v["native"]} for k, v in config.languages_available().items()],
            "support": config.SUPPORT_EMAILS, "version": config.VERSION, "hosted": config.HOSTED}


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


PUBLIC_API = {"/api/login", "/api/ping", "/api/setup"}
_login_hits: dict = {}


@app.middleware("http")
async def _sign_in_required(request: Request, call_next):
    ok, uid = auth.identify(request.cookies)
    path = request.url.path
    if config.HOSTED and path.startswith("/api/") and path not in PUBLIC_API and not ok:
        return JSONResponse({"error": "signin"}, status_code=401)
    token = auth.USER.set(uid)
    try:
        return await call_next(request)
    finally:
        auth.USER.reset(token)


class LoginIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    agree: bool


@app.get("/login")
async def login_page():
    return FileResponse(PWA_DIR / "login.html")


@app.post("/api/login")
async def login(body: LoginIn, request: Request):
    if not config.HOSTED:
        raise HTTPException(404, "not found")
    ip = request.client.host if request.client else "?"
    now = time.monotonic()
    hits = [t for t in _login_hits.get(ip, []) if now - t < 60]
    if len(hits) >= 10:
        raise HTTPException(429, "slow down")
    _login_hits[ip] = hits + [now]
    if not body.agree:
        raise HTTPException(400, "agreement needed")
    if not auth.check_code(body.code):
        raise HTTPException(403, "code")
    resp = JSONResponse({"ok": True})
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(auth.COOKIE, auth.sign(auth.new_user()), max_age=180 * 86400, httponly=True, samesite="lax", secure=secure)
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.delete("/api/me")
async def delete_me():
    uid = auth.USER.get()
    if config.HOSTED and uid:
        auth.delete_user(uid)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE)
    return resp


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
    if config.GROQ_API_KEY or shared or not local or config.HOSTED:
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
