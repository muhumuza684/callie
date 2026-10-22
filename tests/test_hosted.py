"""Hosted mode: invite sign-in, separate data for every person, fair-use limits, delete-my-data."""
from datetime import date

from fastapi.testclient import TestClient

import server.main as srv
from pipeline.runner import VoiceSession
from server import config, limits
from server.main import app


def hosted(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOSTED", True)
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "INVITE_CODES", {"abc123"})
    monkeypatch.setattr(config, "SESSION_SECRET", "s3cret")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(config, "TTS_MODE", "browser")
    limits._active.clear()
    limits._minutes.clear()
    srv._login_hits.clear()


def signed_in(monkeypatch=None):
    c = TestClient(app)
    assert c.post("/api/login", json={"code": "abc123", "agree": True}).status_code == 200
    return c


def test_everything_is_locked_until_sign_in(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    c = TestClient(app)
    assert c.get("/api/state").status_code == 401 and c.get("/health").json() == {"status": "ok"}
    assert c.get("/login").status_code == 200 and "Invite code" in c.get("/login").text
    assert c.post("/api/login", json={"code": "abc123", "agree": False}).status_code == 400      # the consent box is required
    assert c.post("/api/login", json={"code": "wrong", "agree": True}).status_code == 403
    assert c.post("/api/login", json={"code": "abc123", "agree": True}).status_code == 200
    assert c.get("/api/state").json()["hosted"] is True


def test_every_person_has_separate_data(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    a, b = signed_in(), signed_in()
    a.post("/api/contacts", json={"name": "Only-A", "voice": "male"})
    names = lambda c: [x["name"] for x in c.get("/api/state").json()["contacts"]]
    assert "Only-A" in names(a) and "Only-A" not in names(b)
    assert len(list((tmp_path / "users").iterdir())) == 2
    assert all((d / "consent.json").exists() for d in (tmp_path / "users").iterdir())      # the agreement is recorded


def test_a_forged_sign_in_is_refused(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    c = TestClient(app)
    c.cookies.set("callie_session", "0123456789abcdef.deadbeefdeadbeefdeadbeefdeadbeef")
    assert c.get("/api/state").status_code == 401


def test_delete_my_data_removes_everything(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    c = signed_in()
    c.post("/api/contacts", json={"name": "Temp", "voice": "girl"})
    assert len(list((tmp_path / "users").iterdir())) == 1
    assert c.delete("/api/me").status_code == 200
    assert list((tmp_path / "users").iterdir()) == []
    assert c.get("/api/state").status_code == 401


def test_guessing_invite_codes_is_slowed_down(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    c = TestClient(app)
    codes = [c.post("/api/login", json={"code": f"guess{i}", "agree": True}).status_code for i in range(12)]
    assert codes[:10] == [403] * 10 and codes[10] == 429


def test_the_setup_page_is_closed_on_a_server(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    assert TestClient(app).post("/api/setup", json={"key": "gsk_" + "a" * 30}).status_code == 403


def test_calls_need_a_sign_in_and_respect_fair_use(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)
    anon = TestClient(app)
    with anon.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json() == {"type": "notice", "code": "signin"}

    c = signed_in()
    uid = c.cookies.get("callie_session").split(".")[0]
    with c.websocket_connect("/ws/voice") as ws1:
        assert ws1.receive_json()["type"] == "ready"
        with c.websocket_connect("/ws/voice") as ws2:                       # one call at a time per person
            assert ws2.receive_json() == {"type": "notice", "code": "busy"}
        ws1.send_text('{"type":"hangup"}')
    with c.websocket_connect("/ws/voice") as ws3:                            # the slot was given back
        assert ws3.receive_json()["type"] == "ready"
        ws3.send_text('{"type":"hangup"}')

    limits._minutes[(uid, date.today())] = config.LIMIT_MINUTES_PER_DAY + 1
    with c.websocket_connect("/ws/voice") as ws4:
        assert ws4.receive_json() == {"type": "notice", "code": "limit"}


def test_nothing_learned_about_one_person_is_shared_with_another(monkeypatch, tmp_path):
    hosted(monkeypatch, tmp_path)

    async def send(m):
        pass

    class G:
        async def close(self):
            pass

    s1, s2 = VoiceSession(send, groq=G()), VoiceSession(send, groq=G())
    assert s1.profile is not s2.profile and s1.profile.path is None
