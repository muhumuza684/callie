from fastapi.testclient import TestClient

from server import config
from server.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_pwa_served():
    r = client.get("/")
    assert r.status_code == 200 and "Callie" in r.text
    assert client.get("/style.css").headers["cache-control"] == "no-cache"
    for p in ("/app.js", "/worklet.js", "/style.css", "/manifest.json", "/sw.js"):
        assert client.get(p).status_code == 200, p


def test_missing_key_reports_error(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    with client.websocket_connect("/ws/voice") as ws:
        m = ws.receive_json()
        assert m == {"type": "notice", "code": "config"}      # callers never see why, only a friendly code


def test_ready_and_greeting(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "test")
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        assert ws.receive_json()["type"] == "say"
        ws.send_text('{"type":"hangup"}')


def test_pwa_is_installable():
    import json
    m = client.get("/manifest.json").json()
    sizes = {i["sizes"] for i in m["icons"]}
    assert m["display"] == "standalone" and {"192x192", "512x512"} <= sizes
    for i in m["icons"]:
        r = client.get("/" + i["src"])
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert client.get("/icons/apple-touch-icon.png").status_code == 200
