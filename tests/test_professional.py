"""Encapsulation and professionalism: callers see calm wording only; the inside of the system stays hidden."""
import asyncio
import re
from pathlib import Path

from fastapi.testclient import TestClient

from pipeline.runner import VoiceSession
from server import store
from server.groq import ServiceError
from server.main import app

PWA = Path(__file__).resolve().parent.parent / "client" / "pwa"
HTML = (PWA / "index.html").read_text()
JS = (PWA / "app.js").read_text()
CSS = (PWA / "style.css").read_text()
client = TestClient(app)

FORBIDDEN = ["groq", "whisper", "orpheus", "openai", "gpt-oss", "qwen", "cerebras", "llm", "vpn", "api key", "traceback", "stack"]


def test_nothing_technical_in_the_app_text():
    for name, text in (("index.html", HTML), ("app.js", JS)):
        low = text.lower()
        hits = [w for w in FORBIDDEN if w in low]
        assert not hits, f"{name} mentions {hits}"


def test_every_server_code_has_friendly_wording():
    block = re.search(r"const NOTICES = \{(.*?)\n\};", JS, re.S).group(1)
    keys = set(re.findall(r"^\s+(\w+):", block, re.M))
    assert {"net", "busy", "mic", "config", "generic", "micaccess"} <= keys
    for text in re.findall(r':\s+"([^"]+)"', block):
        assert not re.search(r"error|exception|failed|code \d", text, re.I), text


def test_callers_never_receive_raw_error_text():
    class Leaky:
        async def transcribe(self, pcm, lang=None):
            return "hello there friend."

        async def stream_chat(self, messages):
            raise ServiceError("busy", "SECRET-DETAIL api.groq.com 429")
            yield ""

        async def close(self):
            pass

    class Crashy(Leaky):
        async def stream_chat(self, messages):
            raise ValueError("SECRET-TRACE /home/owner/app.py line 12")
            yield ""

    async def go(groq):
        sent = []

        async def send(m):
            sent.append(m)

        await VoiceSession(send, groq=groq).turn(b"\0" * 640)
        return sent

    assert asyncio.run(go(Leaky())) == [{"type": "notice", "code": "busy"}]
    assert asyncio.run(go(Crashy())) == [{"type": "notice", "code": "generic"}]


def test_api_surface_is_not_advertised():
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    assert client.get("/health").json() == {"status": "ok"}
    r = client.post("/api/contacts", json={"name": ""})
    assert r.status_code == 400 and r.json() == {"error": "invalid"}


def test_server_errors_are_generic(monkeypatch):
    quiet = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr(store, "load", lambda: (_ for _ in ()).throw(RuntimeError("SECRET-DB-PATH")))
    r = quiet.get("/api/state")
    assert r.status_code == 500 and r.json() == {"error": "unavailable"} and "SECRET" not in r.text


def test_support_is_one_button_with_the_emails_inside():
    assert 'data-act="support"' in HTML and 'id="sheet-support"' in HTML and 'id="mails"' in HTML
    assert 'data-act="report"' not in HTML                                  # the mail-app link that did not work is gone
    assert "mail.google.com" in JS and "Ref: " in JS and "clipboard" in JS     # Write opens webmail on computers, Copy works anywhere


def test_about_and_faq_are_there_and_say_nothing_technical():
    assert "About Callie" in HTML
    questions = re.findall(r'<details class="faq"><summary>([^<]+)</summary><p>([^<]+)</p>', HTML)
    assert len(questions) == 5
    for q, a in questions:
        assert q.endswith("?") and len(a.split()) >= 30, q          # every question is fully answered


def test_call_screen_has_labelled_buttons_like_a_phone():
    assert "Accept" in JS and "Decline" in JS and '"Mute"' in JS and '"End"' in JS
    assert HTML.index('class="cinfo"') < HTML.index('class="stage"') < HTML.index('id="ctl"')   # name on top, buttons at the bottom


def test_app_fills_the_screen_on_computers():
    assert "@media (min-width:820px)" in CSS and "grid-template-columns" in CSS and 'id="idle"' in HTML
    assert "max-width:none" in CSS
