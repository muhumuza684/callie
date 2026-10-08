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
from server import config, store

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

    who = store.contact(ws.query_params.get("contact"))
    started = time.monotonic()
    session = VoiceSession(send, send_bytes=send_bytes, contact=who, memory_on=store.load()["settings"]["memory"])
    session.ref = ref
    log.info("[%s] call started with %s", ref, who["name"] if who else "default")
    await send({"type": "ready", "voice": session.audio})
    await session.greet()
    try:
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
        try:
            await asyncio.wait_for(session.remember(), 15)
        except Exception as e:
            log.warning("[%s] memory not saved: %r", ref, e)
        await session.close()
        secs = int(time.monotonic() - started)
        log.info("[%s] call ended after %ds", ref, secs)
        if who and secs > 3:
            store.add_recent(who["id"], secs)
