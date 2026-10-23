"""Luganda can be switched on from Settings, by the person at this computer only."""
from fastapi.testclient import TestClient

from server import config
from server.main import app

TOKEN = "aaaaaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbb.cccccccccccccccccccc"


def ready(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOSTED", False)
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "")
    monkeypatch.delenv("SUNBIRD_API_TOKEN", raising=False)
    return TestClient(app)


def langs(c, **kw):
    return [l["id"] for l in c.get("/api/state", **kw).json()["langs"]]


def test_owner_switches_luganda_on_without_a_restart(monkeypatch, tmp_path):
    c = ready(monkeypatch, tmp_path)
    assert "lg" not in langs(c) and c.get("/api/state").json()["owner"] is True
    assert c.post("/api/setup/luganda", json={"token": TOKEN}).json() == {"ok": True}
    assert "lg" in langs(c) and f"SUNBIRD_API_TOKEN={TOKEN}" in (tmp_path / ".env").read_text()


def test_saving_keeps_the_other_settings_and_replaces_an_old_token(monkeypatch, tmp_path):
    c = ready(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text("GROQ_API_KEY=gsk_keep\nSUNBIRD_API_TOKEN=old.old.old")      # even with no newline at the end
    c.post("/api/setup/luganda", json={"token": TOKEN})
    lines = (tmp_path / ".env").read_text().splitlines()
    assert "GROQ_API_KEY=gsk_keep" in lines and lines.count(f"SUNBIRD_API_TOKEN={TOKEN}") == 1 and len(lines) == 2


def test_nobody_coming_through_a_link_can_set_it_or_even_sees_the_row(monkeypatch, tmp_path):
    c = ready(monkeypatch, tmp_path)
    link = {"x-forwarded-for": "203.0.113.7"}
    assert c.post("/api/setup/luganda", json={"token": TOKEN}, headers=link).status_code == 403
    assert c.get("/api/state", headers=link).json()["owner"] is False
    assert not (tmp_path / ".env").exists()


def test_a_hosted_server_never_accepts_it(monkeypatch, tmp_path):
    c = ready(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "HOSTED", True)
    assert c.post("/api/setup/luganda", json={"token": TOKEN}).status_code in (401, 403)


def test_something_that_is_not_a_token_is_refused(monkeypatch, tmp_path):
    c = ready(monkeypatch, tmp_path)
    for bad in ("", "hello", "x" * 60, TOKEN + "\nGROQ_API_KEY=evil", "a.b"):
        assert c.post("/api/setup/luganda", json={"token": bad}).status_code in (400, 422), bad
    assert not (tmp_path / ".env").exists()
