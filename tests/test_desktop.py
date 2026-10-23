"""Desktop app: where data lives, first-run setup, closing with the window."""
import os
from pathlib import Path

from fastapi.testclient import TestClient

from desktop import main as desktop
from server import config
from server.main import STATE, app

client = TestClient(app)


def test_data_lives_in_the_users_folder():
    home = desktop.app_home()
    assert home.name == "Callie"
    assert isinstance(desktop.browser_candidates(), list)
    assert desktop.healthy(1) is False                 # nothing listens there
    assert isinstance(desktop.free_port(8731), int)


def test_ping_marks_the_window_as_open():
    STATE["ping"] = 0.0
    assert client.post("/api/ping").status_code == 200 and STATE["ping"] > 0


def test_first_run_setup_saves_the_key_once(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    key = "gsk_" + "a" * 40
    assert client.get("/setup").status_code == 200 and "Set up Callie" in client.get("/setup").text
    assert client.post("/api/setup", json={"key": "not-a-key"}).status_code == 400
    shared = client.post("/api/setup", json={"key": key}, headers={"x-forwarded-for": "1.2.3.4"})
    assert shared.status_code == 403                                   # never through a shared link
    assert not (tmp_path / ".env").exists()
    assert client.post("/api/setup", json={"key": key}).status_code == 200
    assert f"GROQ_API_KEY={key}" in (tmp_path / ".env").read_text() and config.GROQ_API_KEY == key
    assert client.post("/api/setup", json={"key": "gsk_" + "b" * 40}).status_code == 403   # closed once a key exists


def test_setup_keeps_other_settings(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("STT_LANGUAGE=fr\nGROQ_API_KEY=\n")
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    assert client.post("/api/setup", json={"key": "gsk_" + "c" * 30}).status_code == 200
    text = env.read_text()
    assert "STT_LANGUAGE=fr" in text and text.count("GROQ_API_KEY=") == 1


def test_setup_can_also_save_the_luganda_token(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "")
    monkeypatch.delenv("SUNBIRD_API_TOKEN", raising=False)
    token = "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    for bad in ("hello", "a.b", token + "\nGROQ_API_KEY=evil"):
        assert client.post("/api/setup", json={"key": "gsk_" + "d" * 30, "sunbird": bad}).status_code == 400
    assert not env.exists()                                            # a bad token saves nothing, not even the Groq key
    assert client.post("/api/setup", json={"key": "gsk_" + "d" * 30, "sunbird": token}).status_code == 200
    text = env.read_text()
    assert f"SUNBIRD_API_TOKEN={token}" in text and "GROQ_API_KEY=gsk_" in text and config.SUNBIRD_TOKEN == token


def test_the_token_is_optional_and_the_settings_screen_has_no_luganda_row():
    root = Path(__file__).resolve().parent.parent / "client" / "pwa"
    assert "Luganda" not in (root / "index.html").read_text().split('id="settings"')[1].split("About Callie")[0]
    assert "setup/luganda" not in (root / "app.js").read_text()
    assert 'id="sun"' in (root / "setup.html").read_text()
    assert client.get("/api/state").json().get("owner") is None         # nothing about keys is shown by the app
