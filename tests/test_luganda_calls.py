"""A Luganda contact never breaks anything: without the Sunbird token the call is refused kindly, and does not count."""
from pathlib import Path

from fastapi.testclient import TestClient

from server import config, limits
from server.main import app


def test_a_luganda_call_without_the_token_gets_a_friendly_notice_and_is_not_counted(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOSTED", False)
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "")
    monkeypatch.setattr(config, "CALLS_PER_DEVICE_PER_DAY", 5)
    c = TestClient(app)
    link = {"x-forwarded-for": "203.0.113.7"}
    contact = c.post("/api/contacts", json={"name": "Nabbi", "voice": "female", "lang": "lg"}).json()
    c.get("/api/state", headers=link)
    with c.websocket_connect(f"/ws/voice?contact={contact['id']}", headers=link) as ws:
        assert ws.receive_json() == {"type": "notice", "code": "luganda"}
    assert not (tmp_path / "usage.json").exists()                  # no call was counted
    assert not limits._active                                      # no slot is left taken
    c.delete(f"/api/contacts/{contact['id']}")


def test_the_notice_has_words_in_the_app():
    assert "Luganda is not switched on" in (Path(__file__).resolve().parent.parent / "client" / "pwa" / "app.js").read_text()
