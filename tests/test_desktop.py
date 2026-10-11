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
