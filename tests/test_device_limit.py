"""Five calls per device per day, so the shared access keys last. Direct use on the computer itself is never counted."""
import json

from fastapi.testclient import TestClient

from server import config, limits
from server.main import app

TUNNEL = {"x-forwarded-for": "203.0.113.7"}          # what a phone coming through a tunnel looks like


def setup(monkeypatch, tmp_path, per_day=5):
    monkeypatch.setattr(config, "HOSTED", False)
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "SESSION_SECRET", "s3cret")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(config, "TTS_MODE", "browser")
    monkeypatch.setattr(config, "CALLS_PER_DEVICE_PER_DAY", per_day)
    limits._active.clear()


def long_call(c, headers):
    """A call that lasts long enough to count (the server counts anything over 3 seconds)."""
    return c.websocket_connect("/ws/voice", headers=headers)


def test_a_phone_link_gets_a_device_cookie_and_the_computer_does_not(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    assert limits.DEVICE_COOKIE not in TestClient(app).get("/api/state").cookies
    phone = TestClient(app)
    r = phone.get("/api/state", headers=TUNNEL)
    assert limits.DEVICE_COOKIE in r.cookies and "httponly" in r.headers["set-cookie"].lower()
    assert phone.get("/api/state", headers=TUNNEL).headers.get("set-cookie") is None      # only set once


def test_the_sixth_call_from_one_device_is_refused_and_another_device_is_not(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    monkeypatch.setattr("server.ws.time.monotonic", lambda: next(clock))
    clock = iter(x * 10.0 for x in range(1000))                 # every call looks 10 s long
    phone = TestClient(app)
    phone.get("/api/state", headers=TUNNEL)
    for _ in range(5):
        with long_call(phone, TUNNEL) as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_text('{"type":"hangup"}')
    with long_call(phone, TUNNEL) as ws:
        assert ws.receive_json() == {"type": "notice", "code": "daily"}
    other = TestClient(app)
    other.get("/api/state", headers={"x-forwarded-for": "198.51.100.9"})
    with long_call(other, {"x-forwarded-for": "198.51.100.9"}) as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_text('{"type":"hangup"}')


def test_a_call_that_never_really_started_is_not_counted(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    phone = TestClient(app)
    phone.get("/api/state", headers=TUNNEL)
    for _ in range(8):                                          # hang up at once, eight times
        with long_call(phone, TUNNEL) as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_text('{"type":"hangup"}')
    assert sum(json.loads((tmp_path / "usage.json").read_text())["n"].values()) == 0


def test_clearing_cookies_does_not_give_a_fresh_allowance(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    key = limits.device_key({}, TUNNEL, "10.0.0.1")
    assert key == "a:203.0.113.7"                               # no cookie: counted by address instead
    for _ in range(5):
        limits.device_count(key, +1)
    assert limits.device_can_start(key) == "daily"


def test_the_computer_itself_is_never_limited(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, per_day=1)
    c = TestClient(app)
    for _ in range(3):
        with c.websocket_connect("/ws/voice") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_text('{"type":"hangup"}')


def test_zero_turns_the_limit_off_and_a_new_day_starts_fresh(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, per_day=0)
    limits.device_count("d:x", +50)
    assert limits.device_can_start("d:x") is None
    monkeypatch.setattr(config, "CALLS_PER_DEVICE_PER_DAY", 5)
    assert limits.device_can_start("d:x") == "daily"
    (tmp_path / "usage.json").write_text(json.dumps({"day": "2000-01-01", "n": {"d:x": 99}}))
    assert limits.device_can_start("d:x") is None


def test_a_forged_device_cookie_is_ignored(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    assert limits.device_key({limits.DEVICE_COOKIE: "0123456789abcdef.deadbeef"}, TUNNEL, "x").startswith("a:")
