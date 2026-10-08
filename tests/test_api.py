from fastapi.testclient import TestClient

from server import config, store
from server.main import app

client = TestClient(app)


def test_contacts_schedule_and_recents(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    d = client.get("/api/state").json()
    assert [c["name"] for c in d["contacts"]][:3] == ["Callie", "Mary", "John"]
    c = client.post("/api/contacts", json={"name": "Peter", "voice": "old_man"}).json()
    assert c["voice"] == "old_man" and client.post("/api/contacts", json={"name": "X", "voice": "alien"}).status_code == 400
    s = client.post("/api/schedule", json={"contact": c["id"], "time": "07:30"}).json()
    assert client.post("/api/schedule", json={"contact": c["id"], "time": "7:30"}).status_code == 400
    client.post(f"/api/schedule/{s['id']}/toggle")
    assert client.get("/api/state").json()["schedule"][0]["on"] is False
    client.delete(f"/api/contacts/{c['id']}")
    assert client.get("/api/state").json()["schedule"] == []     # schedule of a deleted contact goes too


def test_call_uses_the_chosen_contact(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    monkeypatch.setattr(config, "GROQ_API_KEY", "test")
    with client.websocket_connect("/ws/voice?contact=mary") as ws:
        assert ws.receive_json()["type"] == "ready"
        assert "Mary" in ws.receive_json()["text"]
        ws.send_text('{"type":"hangup"}')


def test_contact_prompt_and_voice():
    p = config.contact_prompt({"name": "John", "voice": "old_man"})
    assert "You are John," in p and "elderly" in p and "AI" in p
    assert config.pick_voice("male") == "daniel" and config.pick_voice("lady") == "diana"
    assert "age-appropriate" in config.contact_prompt({"name": "Bo", "voice": "baby"})


def test_voice_types_and_shaping():
    girl = config.audio_profile("girl", config.pick_voice("girl"))
    assert girl["gender"] == "f" and girl["rate"] > 1 and girl["pitch"] > 1
    old = config.audio_profile("old_man", config.pick_voice("old_man"))
    assert old["gender"] == "m" and old["rate"] < 1
    v = config.pick_voice("stranger")
    assert v in config.ALL_VOICES and config.audio_profile("stranger", v)["gender"] in ("f", "m")


def test_old_saves_are_migrated(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    (tmp_path / "s.json").write_text(json.dumps({"contacts": [{"id": "x", "name": "X", "voice": "lady", "color": 0}], "recents": [], "schedule": []}))
    assert client.get("/api/state").json()["contacts"][0]["voice"] == "female"
    assert {t["id"] for t in client.get("/api/state").json()["types"]} >= {"baby", "old_lady", "stranger"}


def test_contact_language(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    c = client.post("/api/contacts", json={"name": "Amani", "voice": "female", "lang": "sw"}).json()
    assert c["lang"] == "sw" and client.post("/api/contacts", json={"name": "X", "voice": "male", "lang": "xx"}).status_code == 400
    st = client.get("/api/state").json()
    assert {"sw", "fr", "es", "ar", "zh", "hi", "pt"} <= {l["id"] for l in st["langs"]}
    assert all(x["lang"] for x in st["contacts"])          # older contacts default to English


def test_memory_setting_and_clear(tmp_path, monkeypatch):
    from server import memory
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    monkeypatch.setattr(memory, "PATH", tmp_path / "m.json")
    assert client.get("/api/state").json()["settings"]["memory"] is False          # off by default
    assert client.post("/api/settings", json={"memory": True}).json()["memory"] is True
    memory.put("mary", "likes jazz", [{"role": "user", "content": "hi"}])
    assert memory.get("mary")["summary"] == "likes jazz"
    client.delete("/api/memory")
    assert memory.get("mary")["recent"] == []
    memory.put("john", "x", [])
    client.delete("/api/contacts/john")                                              # deleting a contact deletes its memory
    assert memory.get("john")["summary"] == ""


def test_cannot_delete_the_last_contact(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    ids = [c["id"] for c in client.get("/api/state").json()["contacts"]]
    for cid in ids[:-1]:
        assert client.delete(f"/api/contacts/{cid}").status_code == 200
    assert client.delete(f"/api/contacts/{ids[-1]}").status_code == 409


def test_support_and_version_come_from_the_server(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PATH", tmp_path / "s.json")
    st = client.get("/api/state").json()
    assert st["support"] == ["muhumuzabright26@gmail.com", "brytma616@gmail.com"] and st["version"]
