"""WebSocket transport. Binary in = PCM16 mono 16 kHz (320-sample frames).
JSON out: ready | say | stop | notice(code).  Binary out: 4-byte turn id + WAV (natural voice).  JSON in: tts_state | hangup.
Callers only ever receive short codes; technical detail stays in the owner's log (logs/callie.log)."""
import asyncio
import json
import logging
import re
import time

from fastapi import WebSocket

from pipeline.runner import VoiceSession
from server import auth, config, limits, store

log = logging.getLogger("voice-ai.ws")


async def handle_voice_socket(ws: WebSocket):
    await ws.accept()
    ref = re.sub(r"[^A-Za-z0-9]", "", ws.query_params.get("ref", ""))[:12] or "-"

    async def send(m: dict):
        try:
            await ws.send_text(json.dumps(m))
        except Exception:
            pass

    async def send_bytes(b: bytes):
        try:
            await ws.send_bytes(b)
        except Exception:
            pass

    if not config.GROQ_API_KEY:
        log.error("[%s] OWNER ACTION NEEDED: no GROQ_API_KEY set - run .\\scripts\\configure.ps1 and restart", ref)
        await send({"type": "notice", "code": "config"})
        await ws.close()
        return

    ok, uid = auth.identify(ws.cookies)
    if not ok:
        await send({"type": "notice", "code": "signin"})
        await ws.close()
        return
    auth.USER.set(uid)
    wanted = store.contact(ws.query_params.get("contact"))
    if wanted and wanted.get("lang") == "lg" and not config.SUNBIRD_TOKEN:
        log.warning("[%s] a Luganda call was refused: SUNBIRD_API_TOKEN is not set on this Callie", ref)
        await send({"type": "notice", "code": "luganda"})
        await ws.close()
        return
    dev = limits.device_key(ws.cookies, ws.headers, ws.client.host if ws.client else None) if limits.is_remote(ws.headers) else None
    why = (limits.device_can_start(dev) if dev else None) or limits.can_start(uid)
    if why:
        await send({"type": "notice", "code": why})
        await ws.close()
        return
    limits.start(uid)
    if dev:
        limits.device_count(dev, +1)
    started = time.monotonic()
    session, who = None, None
    try:                      # everything after the slot is taken is inside the try, so the slot is always given back
        who = store.contact(ws.query_params.get("contact"))
        session = VoiceSession(send, send_bytes=send_bytes, contact=who, memory_on=store.load()["settings"]["memory"])
        session.ref = ref
        log.info("[%s] call started with %s", ref, who["name"] if who else "default")
        await send({"type": "ready", "voice": session.audio})
        await session.greet()
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                session.feed(msg["bytes"])
            elif msg.get("text"):
                data = json.loads(msg["text"])
                if data.get("type") == "tts_state":
                    session.set_speaking(bool(data.get("speaking")))
                elif data.get("type") == "hangup":
                    break
    finally:
        if session is not None:
            try:
                await asyncio.wait_for(session.remember(), 15)
            except Exception as e:
                log.warning("[%s] memory not saved: %r", ref, e)
            await session.close()
        secs = int(time.monotonic() - started)
        limits.end(uid, secs)
        if dev and secs <= 3:
            limits.device_count(dev, -1)      # a call that never really started does not use up the day
        log.info("[%s] call ended after %ds", ref, secs)
        if who and secs > 3:
            store.add_recent(who["id"], secs)
