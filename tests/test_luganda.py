"""German, and Luganda through Sunbird AI: optional, isolated, and never able to break the core."""
import asyncio
import json

import httpx

from pipeline.runner import VoiceSession
from server import config
from server.groq import GroqClient, ServiceError


def client_with(handler):
    return GroqClient(transport=httpx.MockTransport(handler))


def test_german_and_luganda_are_always_offered(monkeypatch):
    for token in ("", "tok"):
        monkeypatch.setattr(config, "SUNBIRD_TOKEN", token)
        assert "de" in config.languages_available() and "lg" in config.languages_available()
    assert "Hallo" in config.greeting_for({"name": "Anna", "lang": "de"})


def test_luganda_listening_uses_sunbird(monkeypatch):
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    seen = []

    def handler(req):
        seen.append((req.url.path, req.headers["authorization"], req.content))
        if b'name="file"' not in req.content and b'name="audio"' in req.content and len(seen) == 1:
            return httpx.Response(422, json={"detail": "field required"})        # first field name rejected -> retried
        return httpx.Response(200, json={"audio_transcription": "Oli otya", "language": "lug"})

    async def go():
        g = client_with(handler)
        assert await g.transcribe(b"\0" * 640, "lg") == "Oli otya"
        await g.close()

    asyncio.run(go())
    assert seen[0][0] == "/tasks/audio/transcriptions" and seen[0][1] == "Bearer tok" and b"lug" in seen[0][2]
    assert len(seen) == 2 and b'name="file"' in seen[1][2]


def test_luganda_without_a_token_is_a_quiet_configuration_problem(monkeypatch):
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "")

    async def go():
        g = client_with(lambda r: httpx.Response(500))
        try:
            await g.transcribe(b"\0" * 640, "lg")
        except ServiceError as e:
            return e.code
        finally:
            await g.close()

    assert asyncio.run(go()) == "config"


def test_luganda_voice_downloads_audio_without_sending_any_credentials(monkeypatch):
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    calls = []

    def handler(req):
        calls.append(req)
        if req.url.host == "api.sunbird.ai" and req.url.path == "/tasks/audio/speech":
            return httpx.Response(404)                                                    # newer endpoint missing -> older one
        if req.url.host == "api.sunbird.ai" and req.url.path == "/tasks/tts":
            return httpx.Response(200, json={"output": {"audio_url": "https://files.example.com/a.wav"}})
        return httpx.Response(200, content=b"RIFFluganda")

    async def go():
        g = client_with(handler)
        audio = await g.speak("Oli otya", None, lang="lg")
        await g.close()
        return audio

    assert asyncio.run(go()) == b"RIFFluganda"
    download = calls[-1]
    assert download.url.host == "files.example.com" and "authorization" not in download.headers   # no key ever leaves for another host
    assert calls[0].headers["authorization"] == "Bearer tok"


def test_luganda_contact_asks_the_luganda_model_first_and_falls_back(monkeypatch):
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    monkeypatch.setattr(config, "LLM_CHAIN", "groq:some-model")
    hosts = []

    def handler(req):
        hosts.append(req.url.host)
        if req.url.host == "api.sunbird.ai":
            assert json.loads(req.content)["model"] == config.SUNBIRD_LLM_MODEL
            return httpx.Response(200, content=b"data: [DONE]\n\n")                      # empty answer -> never accepted silently
        return httpx.Response(200, content=b'data: {"choices":[{"delta":{"content":"Weebale."}}]}\n\ndata: [DONE]\n\n')

    async def go():
        g = client_with(handler)
        out = "".join([t async for t in g.stream_chat([{"role": "user", "content": "hi"}], lang="lg")])
        await g.close()
        return out

    assert asyncio.run(go()) == "Weebale." and hosts == ["api.sunbird.ai", "api.groq.com"]


def test_a_service_that_answers_in_one_piece_still_works(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    monkeypatch.setattr(config, "LLM_CHAIN", "groq:m")

    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello there."}}]})

    async def go():
        g = client_with(handler)
        out = "".join([t async for t in g.stream_chat([{"role": "user", "content": "hi"}])])
        await g.close()
        return out

    assert asyncio.run(go()) == "Hello there."


def test_luganda_call_speaks_through_sunbird_without_reading_out_mood_tags(monkeypatch):
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(config, "TTS_MODE", "browser")      # the English voice setting must not matter for Luganda
    spoken, asked = [], []

    class Fake:
        async def transcribe(self, pcm, lang=None):
            assert lang == "lg"
            return "Oli otya."

        async def stream_chat(self, messages, lang=None):
            asked.append((lang, messages))
            yield "[cheerful] Bulungi nnyo. "

        async def speak(self, text, voice=None, lang=None, keep=False):
            spoken.append((text, lang))
            return b"RIFFfake"

        async def close(self):
            pass

    async def go():
        blobs = []

        async def send(m):
            pass

        async def send_bytes(b):
            blobs.append(b)

        s = VoiceSession(send, groq=Fake(), send_bytes=send_bytes,
                         contact={"id": "a", "name": "Amani", "voice": "female", "lang": "lg"})
        assert s.natural()
        await s.turn(b"\0" * 640)
        return blobs

    blobs = asyncio.run(go())
    assert len(blobs) == 1 and spoken == [("Bulungi nnyo.", "lg")]
    system_note = asked[0][1][-1]["content"]
    assert "square brackets" not in system_note                    # mood directions are only for the English voice


def test_luganda_voice_clips_are_remembered_so_the_second_call_is_instant(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    from server import groq
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(groq, "_LUG_VOICE", groq.OrderedDict())
    seen = []

    def handler(req):
        seen.append(req.url.path)
        if req.method == "POST":
            return httpx.Response(200, json={"audio_url": "https://files.example/a.wav"})
        return httpx.Response(200, content=b"RIFFaudio")

    async def go():
        g = client_with(handler)
        a = await g.speak("Oli otya", None, lang="lg", keep=True)
        before = len(seen)
        b = await g.speak("Oli otya", None, lang="lg", keep=True)
        await g.close()
        return a, b, before

    a, b, before = asyncio.run(go())
    assert a == b == b"RIFFaudio" and before == 2 and len(seen) == 2       # the second time nothing was sent to Sunbird


def test_the_luganda_cache_stays_small(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    from server import groq
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(groq, "_LUG_VOICE", groq.OrderedDict())
    monkeypatch.setattr(groq, "_LUG_VOICE_MAX", 3)

    def handler(req):
        return httpx.Response(200, json={"audio_url": "https://files.example/a.wav"}) if req.method == "POST" else httpx.Response(200, content=b"x")

    async def go():
        g = client_with(handler)
        for i in range(6):
            await g.speak(f"phrase {i}", None, lang="lg", keep=True)
        await g.close()

    asyncio.run(go())
    assert list(groq._LUG_VOICE) == ["phrase 3", "phrase 4", "phrase 5"]


def test_greetings_are_prepared_ahead_of_time_only_for_luganda_contacts(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    from pipeline.runner import prewarm_luganda
    from server import groq
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(groq, "_LUG_VOICE", groq.OrderedDict())
    posts = []

    def handler(req):
        if req.method == "POST":
            posts.append(1)
            return httpx.Response(200, json={"audio_url": "https://files.example/a.wav"})
        return httpx.Response(200, content=b"x")

    contacts = [{"name": "Nalu", "lang": "lg", "voice": "female"}, {"name": "Anna", "lang": "de", "voice": "female"}]
    asyncio.run(prewarm_luganda(contacts, transport=httpx.MockTransport(handler)))
    assert len(posts) == 1 and len(groq._LUG_VOICE) == 1                  # German is untouched
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "")
    asyncio.run(prewarm_luganda(contacts, transport=httpx.MockTransport(lambda r: 1 / 0)))     # no token: nothing is attempted


def test_a_failed_preparation_never_breaks_startup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    from pipeline.runner import prewarm_luganda
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    asyncio.run(prewarm_luganda([{"name": "Nalu", "lang": "lg", "voice": "female"}], transport=httpx.MockTransport(lambda r: httpx.Response(500))))


def test_only_the_greeting_is_remembered_never_what_is_said_in_a_conversation(monkeypatch, tmp_path):
    from server import groq
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(groq, "_LUG_VOICE", groq.OrderedDict())
    posts = []

    def handler(req):
        if req.method == "POST":
            posts.append(1)
            return httpx.Response(200, json={"audio_url": "https://files.example/a.wav"})
        return httpx.Response(200, content=b"RIFFaudio")

    async def go():
        g = client_with(handler)
        await g.speak("a private reply", None, lang="lg")                 # a conversation line
        await g.speak("a private reply", None, lang="lg")
        await g.speak("Oli otya, nze Nalu", None, lang="lg", keep=True)   # the greeting
        await g.close()

    asyncio.run(go())
    assert len(posts) == 3                                                # the conversation line was made both times
    assert list(groq._LUG_VOICE) == ["Oli otya, nze Nalu"]
    assert len(list((tmp_path / "cache").glob("lg-*.wav"))) == 1


def test_a_saved_greeting_is_used_after_a_restart_and_the_disk_cache_stays_small(monkeypatch, tmp_path):
    from server import groq
    monkeypatch.setattr(config, "SUNBIRD_TOKEN", "tok")
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(groq, "_LUG_DISK_MAX", 3)
    monkeypatch.setattr(groq, "_LUG_VOICE", groq.OrderedDict())
    calls = []

    def handler(req):
        calls.append(req.method)
        return httpx.Response(200, json={"audio_url": "https://files.example/a.wav"}) if req.method == "POST" else httpx.Response(200, content=b"RIFFaudio")

    async def go(texts):
        g = client_with(handler)
        for t in texts:
            await g.speak(t, None, lang="lg", keep=True)
        await g.close()

    asyncio.run(go(["one"]))
    monkeypatch.setattr(groq, "_LUG_VOICE", groq.OrderedDict())            # the app was closed and opened again
    before = len(calls)
    asyncio.run(go(["one"]))
    assert len(calls) == before                                           # read from disk, Sunbird was not asked
    asyncio.run(go(["two", "three", "four", "five"]))
    assert len(list((tmp_path / "cache").glob("lg-*.wav"))) == 3


def test_luganda_gets_more_time_to_listen_and_no_wrong_language_filler():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent / "pipeline" / "runner.py").read_text()
    assert "STT_TIMEOUTS_LG = (20, 30)" in src and 'STT_TIMEOUTS_LG if self.lang == "lg"' in src
    assert 'if self.lang == "lg":' in src.split("async def _filler")[1].split("async def remember")[0]
    app = (pathlib.Path(__file__).resolve().parent.parent / "client" / "pwa" / "app.js").read_text()
    assert 'base !== "lg"' in app
