"""Groq client (free tier): Whisper STT, Orpheus TTS, and the LLM fallback chain.
Failures raise ServiceError(code); the code is all a caller ever sees - details go to the owner's log only."""
import json
import logging
from typing import AsyncIterator

import httpx

from audio.pcm import pcm_to_wav
from server import config
from server.llm import ThinkStripper, llm_chain

log = logging.getLogger("voice-ai.groq")
BASE = "https://api.groq.com/openai/v1"


class ServiceError(RuntimeError):
    """code: net | busy | config | voice | generic  (mapped to friendly wording in the app)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


class ModelGone(ServiceError):
    def __init__(self, detail: str = ""):
        super().__init__("busy", detail)


def _net(e: Exception) -> ServiceError:
    log.warning("Connection problem: %r (check internet / VPN)", e)
    return ServiceError("net", repr(e))


def _fail(status: int, body: str, chat: bool = False):
    if chat and status in (400, 403, 404) and "model" in body.lower():
        raise ModelGone(body[:150])
    if status == 401:
        raise ServiceError("config", "API key rejected")
    if status == 429:
        raise ServiceError("busy", "rate limit reached")
    raise ServiceError("generic", f"error {status}: {body[:150]}")


class GroqClient:
    def __init__(self, transport=None):
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=30.0),   # patient: slow links need long TLS handshakes
            transport=transport or httpx.AsyncHTTPTransport(retries=3),
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        )

    async def warm(self):
        """Open the TLS connection at call start so the first reply isn't slowed by the handshake."""
        try:
            await self.http.get(f"{BASE}/models")
        except Exception as e:
            log.warning("Groq warm-up failed: %r", e)

    async def transcribe(self, pcm: bytes, lang: str | None = None) -> str:
        language = lang or config.STT_LANGUAGE
        data = {"model": config.STT_MODEL, "temperature": "0", "response_format": "verbose_json"}
        if language:
            data["language"] = language
        if config.STT_HINT and language in ("", "en", None):
            data["prompt"] = config.STT_HINT      # biases spelling of names and terms (English only)
        try:
            r = await self.http.post(f"{BASE}/audio/transcriptions", data=data,
                                     files={"file": ("speech.wav", pcm_to_wav(pcm), "audio/wav")})
        except httpx.TransportError as e:
            raise _net(e) from None
        if r.status_code != 200:
            _fail(r.status_code, r.text)
        j = r.json()
        segs = j.get("segments") or []
        # Whisper invents text ("Thank you.") on noise. Drop clips it itself says are not speech.
        if segs and all(sg.get("no_speech_prob", 0) > 0.6 for sg in segs):
            return ""
        if segs and all(sg.get("avg_logprob", 0) < -1.0 for sg in segs):
            return ""
        return j.get("text", "").strip()

    async def stream_chat(self, messages: list) -> AsyncIterator[str]:
        """Try each model in LLM_CHAIN until one answers; switching is only possible before the first word."""
        errors, codes = [], []
        for prov, model, base, key in llm_chain():
            started = False
            try:
                async for tok in self._stream(prov, model, base, key, messages):
                    started = True
                    yield tok
                return
            except ServiceError as e:
                if started:
                    raise
                log.warning("AI model %s:%s failed (%s) - trying the next one", prov, model, e)
                errors.append(f"{prov}:{model}")
                codes.append(e.code)
        code = "config" if not errors else ("net" if "net" in codes else "busy")
        raise ServiceError(code, "No AI model answered (" + ", ".join(errors or ["none configured"]) + ")")

    async def _stream(self, prov, model, base, key, messages) -> AsyncIterator[str]:
        body = {"model": model, "messages": messages, "stream": True, "max_tokens": 700, "temperature": 0.7}
        if prov == "groq" and model.startswith("openai/gpt-oss") and config.REASONING_EFFORT:
            body["reasoning_effort"] = config.REASONING_EFFORT   # short thinking = faster voice replies
        if prov == "groq" and "qwen3" in model:
            body["reasoning_effort"] = "none"
        strip = ThinkStripper()
        try:
            async with self.http.stream("POST", f"{base}/chat/completions", json=body,
                                        headers={"Authorization": f"Bearer {key}"}) as r:
                if r.status_code != 200:
                    _fail(r.status_code, (await r.aread()).decode("utf-8", "ignore"), chat=True)
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    d = line[5:].strip()
                    if d == "[DONE]":
                        break
                    choices = json.loads(d).get("choices") or [{}]
                    tok = (choices[0].get("delta") or {}).get("content")
                    if tok:
                        out = strip.feed(tok)
                        if out:
                            yield out
        except httpx.TransportError as e:
            raise _net(e) from None
        tail = strip.flush()
        if tail:
            yield tail

    async def speak(self, text: str, voice: str | None = None) -> bytes:
        """Orpheus text-to-speech (English, max ~200 chars per request). Returns WAV bytes."""
        body = {"model": config.TTS_MODEL, "voice": voice or config.TTS_VOICE, "input": text, "response_format": "wav"}
        try:
            r = await self.http.post(f"{BASE}/audio/speech", json=body)
        except httpx.TransportError as e:
            raise _net(e) from None
        if r.status_code == 429:
            raise ServiceError("voice", "voice limit reached (free tier: 10 requests/min, 100/day)")
        if r.status_code != 200:
            if "terms" in r.text.lower():
                raise ServiceError("voice", "accept the Orpheus model terms in the Groq console (Playground > Text to Speech)")
            raise ServiceError("voice", f"voice error {r.status_code}: {r.text[:100]}")
        return r.content

    async def close(self):
        await self.http.aclose()
