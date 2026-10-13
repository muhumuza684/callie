import asyncio
import struct

import numpy as np

from audio.pcm import float_to_pcm16
from pipeline.runner import VoiceSession, pack_chunks, plain, pop_sentence
from server import config

config.TTS_MODE = "browser"   # most tests use the basic voice path
import conversation.profile as _cp

_cp.PROFILE_PATH = None       # tests must not write a real profile


class FakeGroq:
    async def close(self):
        pass


def frames(level, n):
    t = np.arange(320) / 16000
    return [float_to_pcm16(level * np.sin(2 * np.pi * 220 * t).astype("f4"))] * n


def test_pop_sentence():
    assert pop_sentence("Hi there. How are") == ("Hi there. ", "How are", True)
    assert pop_sentence("x" * 50 + ", " + "y" * 80)[2] is False
    assert pop_sentence("Pi is 3.14 roughly") is None


def test_one_utterance_triggers_one_turn():
    async def go():
        calls = []

        async def send(m):
            pass

        async def fake_turn(pcm, voiced=99):
            calls.append(len(pcm))

        s = VoiceSession(send, groq=FakeGroq())
        s.turn = fake_turn
        for f in frames(0.0, 10) + frames(0.3, 30) + frames(0.0, 40):
            s.feed(f)
        await asyncio.sleep(0.05)
        assert len(calls) == 1

    asyncio.run(go())


def test_blip_ignored_and_barge_in():
    async def go():
        sent = []

        async def send(m):
            sent.append(m)

        s = VoiceSession(send, groq=FakeGroq())
        for f in frames(0.0, 10) + frames(0.3, 4) + frames(0.0, 40):
            s.feed(f)
        assert s.task is None  # 80 ms blip: no turn
        s.set_speaking(True)
        for f in frames(0.5, 14):
            s.feed(f)
        await asyncio.sleep(0.05)
        assert any(m["type"] == "stop" for m in sent) and not s.client_speaking

    asyncio.run(go())


def test_network_error_reaches_client():
    import httpx

    class Broken(FakeGroq):
        async def transcribe(self, pcm, lang=None):
            from server.groq import ServiceError
            raise ServiceError("net", "connect timeout to api.example")

    async def go():
        sent = []

        async def send(m):
            sent.append(m)

        s = VoiceSession(send, groq=Broken())
        await s.turn(b"\0" * 640)
        assert sent == [{"type": "notice", "code": "net"}]       # a code only: no host names, no advice about VPNs

    asyncio.run(go())


def test_llm_chain_falls_through(monkeypatch):
    import json

    import httpx

    from server.groq import GroqClient

    monkeypatch.setattr(config, "LLM_CHAIN", "groq:dead-model,openrouter:no-key-model,cerebras:good-model")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k1")
    monkeypatch.setenv("CEREBRAS_API_KEY", "k2")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    calls = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        calls.append((req.url.host, body["model"], req.headers["authorization"]))
        if body["model"] == "dead-model":
            return httpx.Response(404, json={"error": {"message": "The model `dead-model` does not exist"}})
        sse = 'data: {"choices":[{"delta":{"content":"<think>hmm</think>Hi there."}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=sse.encode())

    async def go():
        g = GroqClient(transport=httpx.MockTransport(handler))
        out = [t async for t in g.stream_chat([{"role": "user", "content": "hi"}])]
        assert "".join(out) == "Hi there."
        assert [c[0] for c in calls] == ["api.groq.com", "api.cerebras.ai"]      # the keyless provider was skipped
        assert calls[1][2] == "Bearer k2"
        await g.close()

    asyncio.run(go())


def test_think_stripper_handles_split_tags():
    from server.llm import ThinkStripper

    t = ThinkStripper()
    out = "".join(t.feed(x) for x in ["<thi", "nk>secret</thi", "nk>Hel", "lo <b", "ye"]) + t.flush()
    assert out == "Hello <bye"


def test_other_language_greeting_and_no_orpheus():
    async def go():
        config.TTS_MODE = "orpheus"
        try:
            sent = []

            async def send(m):
                sent.append(m)

            s = VoiceSession(send, groq=VoiceGroq([]), contact={"id": "m", "name": "Mary", "voice": "female", "lang": "sw"})
            assert not s.natural() and s.audio["lang"] == "sw-KE"
            await s.greet()
            assert "Mary" in sent[0]["text"] and "AI" in sent[0]["text"]
            assert "Swahili" in s.history[0]["content"]
        finally:
            config.TTS_MODE = "browser"

    asyncio.run(go())


def test_silent_microphone_is_logged_but_never_alarms_the_caller(caplog):
    async def go():
        sent = []

        async def send(m):
            sent.append(m)

        s = VoiceSession(send, groq=FakeGroq())
        for f in frames(0.0, 500):
            s.feed(f)
        await asyncio.sleep(0.05)
        return sent

    import logging
    with caplog.at_level(logging.WARNING, logger="voice-ai.session"):
        sent = asyncio.run(go())
    assert not [m for m in sent if m["type"] in ("notice", "error")]       # phones send exact zeros while you are quiet
    assert "only silence" in caplog.text


def test_whisper_noise_filtered():
    import httpx

    from server.groq import GroqClient

    def handler(req):
        return httpx.Response(200, json={"text": "Thank you.", "segments": [{"no_speech_prob": 0.9, "avg_logprob": -0.4}]})

    async def go():
        g = GroqClient(transport=httpx.MockTransport(handler))
        assert await g.transcribe(b"\0" * 640) == ""
        await g.close()

    asyncio.run(go())


class ScriptedGroq(FakeGroq):
    def __init__(self, texts):
        self.texts, self.asked, self.msgs = list(texts), [], []

    async def transcribe(self, pcm, lang=None):
        return self.texts.pop(0)

    async def stream_chat(self, messages):
        self.msgs = messages
        self.asked.append([m for m in messages if m["role"] == "user"][-1]["content"])
        yield "Okay. "


def test_unfinished_phrase_is_held_and_merged():
    import pipeline.runner as r

    async def go():
        r.HOLD_SECONDS = 0.05
        g = ScriptedGroq(["I think", "I have some tasks."])

        async def send(m):
            pass

        s = VoiceSession(send, groq=g)
        t1 = asyncio.create_task(s.turn(b"\0" * 640))
        await asyncio.sleep(0.01)
        assert s.holding and not s.ai_active
        t1.cancel()                       # caller kept talking
        await asyncio.gather(t1, return_exceptions=True)
        await s.turn(b"\0" * 640)
        assert g.asked == ["I think I have some tasks."]

    asyncio.run(go())


def test_unfinished_phrase_answered_after_hold():
    import pipeline.runner as r

    async def go():
        r.HOLD_SECONDS = 0.02
        g = ScriptedGroq(["Hello there"])

        async def send(m):
            pass

        s = VoiceSession(send, groq=g)
        await s.turn(b"\0" * 640)
        assert g.asked == ["Hello there"]

    asyncio.run(go())


def test_reply_is_capped_and_cleaned_and_prompt_kept():
    from pipeline.runner import clean

    assert clean("**Hi** | there \U0001F680 ---") == "Hi there"

    class Chatty(ScriptedGroq):
        async def stream_chat(self, messages):
            self.msgs = messages
            for i in range(8):
                yield f"Sentence {i}. "

    async def go():
        sent = []

        async def send(m):
            sent.append(m)

        g = Chatty(["Tell me everything about it please."])
        s = VoiceSession(send, groq=g)
        for i in range(10):   # long history must not push the system prompt out
            s.history += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
        await s.turn(b"\0" * 640)
        says = [m for m in sent if m["type"] == "say"]
        from pipeline.runner import MAX_SENTENCES
        assert len(says) == MAX_SENTENCES == 7
        assert g.msgs[0]["role"] == "system" and "voice" in g.msgs[0]["content"].lower()

    asyncio.run(go())


def test_filler_ignored():
    async def go():
        g = ScriptedGroq(["and"])
        sent = []

        async def send(m):
            sent.append(m)

        s = VoiceSession(send, groq=g)
        await s.turn(b"\0" * 640)
        assert g.asked == [] and not sent

    asyncio.run(go())


def test_pack_chunks_and_plain():
    ch = pack_chunks(["Hello there. ", "[sad] I am sorry.", "x" * 450])
    assert all(len(c) <= 190 for c in ch) and ch[0].startswith("Hello there. [sad]")
    assert plain("[laughing] Ha ha! (laughs) Good one.") == "Ha ha! Good one."


class VoiceGroq(ScriptedGroq):
    def __init__(self, texts, fail=False):
        super().__init__(texts)
        self.fail = fail

    async def speak(self, text, voice=None):
        if self.fail:
            raise RuntimeError("voice limit reached")
        return b"RIFFfakewav"


def test_natural_voice_sends_audio():
    async def go():
        config.TTS_MODE = "orpheus"
        try:
            sent, blobs = [], []

            async def send(m):
                sent.append(m)

            async def send_bytes(b):
                blobs.append(b)

            s = VoiceSession(send, groq=VoiceGroq(["Tell me a joke."]), send_bytes=send_bytes)
            await s.turn(b"\0" * 640)
            assert len(blobs) == 1 and blobs[0][4:] == b"RIFFfakewav" and struct.unpack(">I", blobs[0][:4])[0] == 0
            assert not [m for m in sent if m["type"] == "say"]
        finally:
            config.TTS_MODE = "browser"

    asyncio.run(go())


def test_natural_voice_falls_back_to_browser_voice():
    async def go():
        config.TTS_MODE = "orpheus"
        try:
            sent = []

            async def send(m):
                sent.append(m)

            s = VoiceSession(send, groq=VoiceGroq(["Tell me a joke."], fail=True))
            await s.turn(b"\0" * 640)
            kinds = [m["type"] for m in sent]
            assert "say" in kinds and "error" not in kinds and "notice" not in kinds and not s.natural()
        finally:
            config.TTS_MODE = "browser"

    asyncio.run(go())


def test_stalled_transcription_is_retried():
    import pipeline.runner as r

    class Slow(ScriptedGroq):
        calls = 0

        async def transcribe(self, pcm, lang=None):
            Slow.calls += 1
            if Slow.calls == 1:
                await asyncio.sleep(10)
            return "How are you?"

    async def go():
        old = r.STT_TIMEOUTS
        r.STT_TIMEOUTS = (0.05, 1)
        try:
            g = Slow([])

            async def send(m):
                pass

            await VoiceSession(send, groq=g).turn(b"\0" * 640)
            assert Slow.calls == 2 and g.asked == ["How are you?"]
        finally:
            r.STT_TIMEOUTS = old

    asyncio.run(go())


def test_terms_error_stops_retrying_voice():
    class NoTerms(VoiceGroq):
        async def speak(self, text, voice=None):
            raise RuntimeError("accept the Orpheus model terms in the Groq console")

    async def go():
        config.TTS_MODE = "orpheus"
        try:
            sent = []

            async def send(m):
                sent.append(m)

            s = VoiceSession(send, groq=NoTerms(["Hello there."]))
            await s.turn(b"\0" * 640)
            assert VoiceSession.voice_blocked and not s.natural()
            assert not any(m["type"] in ("error", "notice") for m in sent)        # the caller is never told
        finally:
            config.TTS_MODE = "browser"
            VoiceSession.voice_blocked = False

    asyncio.run(go())


def test_slow_reply_gets_a_filler():
    import pipeline.runner as r

    class Slowish(ScriptedGroq):
        async def stream_chat(self, messages):
            await asyncio.sleep(0.2)
            yield "Okay. "

    async def go():
        old = r.FILLER_AFTER
        r.FILLER_AFTER = 0.05
        try:
            sent = []

            async def send(m):
                sent.append(m)

            await VoiceSession(send, groq=Slowish(["Tell me something."])).turn(b"\0" * 640)
            texts = [m["text"] for m in sent if m["type"] == "say"]
            assert texts[0] == "One moment." and "Okay." in texts[1]
        finally:
            r.FILLER_AFTER = old

    asyncio.run(go())


def test_stuck_speaking_state_expires():
    async def go():
        async def send(m):
            pass

        s = VoiceSession(send, groq=FakeGroq())
        s.set_speaking(True)
        assert s.ai_active
        s.speaking_until -= 100            # the browser never sent 'finished'
        assert not s.ai_active

    asyncio.run(go())


def test_memory_roundtrip_between_calls(tmp_path, monkeypatch):
    from server import memory
    monkeypatch.setattr(memory, "PATH", tmp_path / "m.json")

    class Teller(ScriptedGroq):
        async def stream_chat(self, messages):
            self.msgs = messages
            if messages[0]["content"].startswith("You keep a private memory"):
                yield "Caller loves jazz."
            else:
                yield "Okay. "

    contact = {"id": "mary", "name": "Mary", "voice": "female", "lang": "en"}

    async def go():
        async def send(m):
            pass

        s1 = VoiceSession(send, groq=Teller(["I love jazz music.", "Play me something."]), contact=contact, memory_on=True)
        await s1.turn(b"\0" * 640)
        await s1.turn(b"\0" * 640)
        await s1.remember()
        assert memory.get("mary")["summary"] == "Caller loves jazz." and len(memory.get("mary")["recent"]) == 4

        s2 = VoiceSession(send, groq=Teller([]), contact=contact, memory_on=True)      # next call continues
        assert "loves jazz" in s2.history[0]["content"] and s2.history[1]["content"] == "I love jazz music."

        s3 = VoiceSession(send, groq=Teller(["Hello there friend."]), contact=contact, memory_on=False)
        assert "loves jazz" not in s3.history[0]["content"] and len(s3.history) == 1    # off = nothing remembered
        await s3.turn(b"\0" * 640)
        await s3.remember()
        assert len(memory.get("mary")["recent"]) == 4                                   # and nothing saved

    asyncio.run(go())
