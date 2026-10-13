"""Live call session: frames in -> VAD turn-taking -> STT -> LLM -> sentences out.
The browser speaks the sentences (speechSynthesis). Barge-in cancels the turn."""
import asyncio
from contextlib import aclosing
import collections
import logging
import re
import struct
import time

import numpy as np

from audio.pcm import pcm16_to_float
from audio.voice_features import Baseline, analyze
from conversation.profile import default_profile, is_laughing, text_mood
from server import config, memory
from server.groq import GroqClient, ServiceError

log = logging.getLogger("voice-ai.session")

PREROLL_FRAMES = 12      # 240 ms kept from before speech was detected
SILENCE_FRAMES = 32      # 640 ms of quiet ends the utterance
MIN_VOICED_FRAMES = 12   # ignore blips shorter than ~250 ms
START_FRAMES = 3         # 60 ms of speech starts an utterance
BARGE_FRAMES = 12        # 240 ms of loud speech interrupts the AI
HALLUCINATIONS = {"you", "bye", "thanks for watching", "thank you for watching"}
FILLER = {"and", "but", "so", "the", "a", "i", "um", "uh", "hmm", "mm", "oh", "then"}
MAX_SENTENCES = 7        # safety cap: a spoken answer, never an essay
DIRECTIONS = ("You may open a sentence with one single-word direction in square brackets, like [cheerful], [sad], "
              "[excited], [whisper] or [laughing], when the emotion fits; use it sparingly. "
              "If asked to act out an emotion, perform it briefly in a line. Never write actions in parentheses.")
REMINDER = ("Voice call. Usually answer in one or two short spoken sentences. If the caller asks for a story, "
            "explanation or detail, tell it properly in up to six short sentences and finish the thought. "
            "If unsure of a fact, say so instead of inventing details. If the words don't make sense, say you didn't catch that. "
            "No markdown, tables, lists, headings or emojis.")
SHORT_NOISE = {"thank you", "thanks", "yeah", "yes", "oh", "so", "okay", "ok", "uh", "um", "hmm"}
STT_TIMEOUTS = (8, 12)   # seconds: try, then retry once, so a stalled connection never freezes the call
FILLER_AFTER = 4.0       # say 'One moment.' if nothing has happened this long after you stop
HOLD_SECONDS = 1.0       # wait this long after an unfinished-sounding phrase ("I think...")
_SENT = re.compile(r'[.!?]+["\')\]]*\s')


def pop_sentence(buf: str):
    """Returns (chunk, rest, is_sentence_end). Long sentences are also split at commas so speech starts early."""
    m = _SENT.search(buf)
    if m:
        return buf[:m.end()], buf[m.end():], True
    if len(buf) > 110 and "," in buf[40:]:
        i = buf.rfind(",", 40) + 1
        return buf[:i], buf[i:], False
    return None


def clean(text: str) -> str:
    text = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f]", "", text)   # emojis
    text = re.sub(r"-{3,}|[*#`_~|]", " ", text)                                   # markdown/table marks
    return re.sub(r"\s+", " ", text).strip()


def plain(text: str) -> str:
    """Text for the basic browser voice: no [directions], no (stage actions)."""
    text = re.sub(r"\[[^\]]*\]", "", clean(text))
    text = re.sub(r"\((?:laughs?|laughing|giggles?|sighs?|cries|crying|claps|smiles|chuckles)\)", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def pack_chunks(sentences, limit: int = 190):
    """Group sentences into pieces that fit one voice request (Orpheus allows ~200 characters)."""
    chunks, cur = [], ""
    for s in (x.strip() for x in sentences if x.strip()):
        while len(s) > limit:
            cut = s.rfind(" ", 0, limit)
            cut = cut if cut > 20 else limit
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if len(cur) + len(s) + 1 <= limit:
            cur = f"{cur} {s}".strip()
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return chunks


class VoiceSession:
    voice_blocked = False   # set when Groq says the voice terms are not accepted (stop retrying)
    def __init__(self, send, groq=None, send_bytes=None, profile=None, contact=None, memory_on=False):
        self.send = send
        self.contact = contact
        self.lang = (contact or {}).get("lang") or None      # None = default (English / .env)
        self.en = (self.lang or "en") == "en"
        self.voice = config.pick_voice(contact["voice"]) if contact else None
        self.audio = (config.audio_profile(contact["voice"], self.voice) if contact
                      else {"rate": 1.0, "pitch": 1.0, "speech": 1.0, "gender": "f"})
        self.speaking_until, self._frames, self._peak, self._max_all = 0.0, 0, 0.0, 0.0
        self.ref = "-"        # support reference of the caller's device, used only in the owner's log
        self.audio["lang"] = config.lang_info(self.lang)["bcp47"]
        self.baseline = Baseline()
        self.profile = profile or default_profile()

        async def _nobytes(b):
            pass
        self.send_bytes = send_bytes or _nobytes
        self.tts_off_until = 0.0
        self.groq = groq or GroqClient()
        self.history = [{"role": "system", "content": config.contact_prompt(contact) if contact else config.SYSTEM_PROMPT}]
        self.memory_on = bool(memory_on and contact)
        if self.memory_on:        # optional: continue earlier conversations with this contact
            m = memory.get(contact["id"])
            if m["summary"]:
                self.history[0]["content"] += " What you remember from earlier calls with this caller (use it naturally, never recite it): " + m["summary"]
            self.history += [dict(x) for x in m["recent"][-8:]]
        self._start = len(self.history)
        self.preroll = collections.deque(maxlen=PREROLL_FRAMES)
        self.buf, self.in_speech = [], False
        self.run = self.silence = self.voiced = 0
        self.noise = 0.01
        self.turn_id = 0
        self.task = None
        self.client_speaking = False
        self.pending, self.pending_t, self.holding = "", 0.0, False

    # ---- state ----
    @property
    def ai_active(self) -> bool:
        busy = self.task is not None and not self.task.done() and not self.holding
        # "browser is speaking" expires on its own so a lost end-event can never mute the caller
        return busy or (self.client_speaking and time.monotonic() < self.speaking_until)

    def set_speaking(self, on: bool):
        self.client_speaking = on
        self.speaking_until = time.monotonic() + 15

    async def greet(self):
        if hasattr(self.groq, "warm"):
            asyncio.get_running_loop().create_task(self.groq.warm())
        greeting = config.greeting_for(self.contact) if self.contact else config.GREETING
        if not greeting:
            return
        if self.natural():
            self.task = asyncio.get_running_loop().create_task(self.speak_chunks(self.turn_id, [greeting], 0.0))
        else:
            await self.send({"type": "say", "turn": self.turn_id, "text": plain(greeting)})

    def natural(self) -> bool:
        return (config.TTS_MODE == "orpheus" and self.en and not VoiceSession.voice_blocked and hasattr(self.groq, "speak")
                and time.monotonic() >= self.tts_off_until)

    async def speak_chunks(self, tid: int, sentences, t0: float):
        chunks = pack_chunks(sentences)
        tasks = [asyncio.get_running_loop().create_task(self.groq.speak(c, self.voice)) for c in chunks]
        for t in tasks:
            t.add_done_callback(lambda f: f.cancelled() or f.exception())
        try:
            for i, (chunk, t) in enumerate(zip(chunks, tasks)):
                try:
                    wav = await t
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    reason = str(e) or type(e).__name__
                    if "terms" in reason:       # the caller is never told: the basic voice simply takes over
                        log.error("[%s] OWNER ACTION NEEDED: accept the Orpheus voice terms in the Groq console; using the basic voice until then", self.ref)
                        VoiceSession.voice_blocked = True
                    else:
                        log.warning("[%s] natural voice unavailable (%s); basic voice for 90 s", self.ref, reason)
                        self.tts_off_until = time.monotonic() + 90
                    for rest in chunks[i:]:
                        if plain(rest):
                            await self.send({"type": "say", "turn": tid, "text": plain(rest)})
                    return
                if i == 0 and t0:
                    log.info("first audio ready %.1fs after you stopped talking", time.monotonic() - t0)
                await self.send_bytes(struct.pack(">I", tid) + wav)
        finally:
            for t in tasks:
                t.cancel()

    async def hear(self, pcm: bytes) -> str:
        for timeout in STT_TIMEOUTS:
            try:
                return await asyncio.wait_for(self.groq.transcribe(pcm, self.lang), timeout)
            except (asyncio.TimeoutError, TimeoutError):
                log.warning("transcription stalled (> %ss), retrying", timeout)
        raise ServiceError("net", "transcription timed out twice")

    async def _filler(self, tid: int):
        await asyncio.sleep(FILLER_AFTER)
        await self.send({"type": "say", "turn": tid, "text": config.lang_info(self.lang)["wait"]})

    async def remember(self):
        """Save notes about this call (only when memory is on)."""
        new = [m for m in self.history[self._start:] if m["role"] in ("user", "assistant")]
        if not self.memory_on or not any(m["role"] == "user" for m in new):
            return
        cid, old = self.contact["id"], memory.get(self.contact["id"])
        recent = old["recent"] + [{"role": m["role"], "content": m["content"][:400]} for m in new]
        summary = old["summary"]
        if sum(m["role"] == "user" for m in new) >= 2:
            try:
                talk = "\n".join(f"{'Caller' if m['role'] == 'user' else self.contact['name']}: {m['content'][:300]}" for m in new)
                ask = [{"role": "system", "content": "You keep a private memory for a voice companion. Update it in at most 4 short sentences: "
                        "facts about the caller (name, interests, plans), topics discussed, promises made. No advice, no quotes."},
                       {"role": "user", "content": f"Existing memory: {old['summary'] or 'none'}\n\nLatest call:\n{talk}\n\nUpdated memory:"}]
                out = ""
                async with aclosing(self.groq.stream_chat(ask)) as stream:
                    async for tok in stream:
                        out += tok
                if out.strip():
                    summary = out.strip()
            except Exception as e:
                log.warning("memory summary failed: %s", e)
        memory.put(cid, summary, recent)

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
        await self.groq.close()

    # ---- audio in ----
    def feed(self, frame: bytes):
        x = pcm16_to_float(frame)
        rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
        active = self.ai_active
        thr = max(0.012, self.noise * 3.0) * (2.5 if active else 1.0)
        loud = rms > thr
        self._frames += 1
        self._peak = max(self._peak, rms)
        self._max_all = max(self._max_all, rms)
        if self._frames == 500 and self._max_all < 0.0005:     # only logged: phones often send exact zeros while the caller is quiet
            log.warning("[%s] the microphone has sent only silence for 10 s", self.ref)
        if self._frames % 250 == 0:      # every 5 s: shows whether your voice reaches the server
            log.info("mic: peak %.3f, threshold %.3f, noise %.3f, ai_active=%s", self._peak, thr, self.noise, active)
            self._peak = 0.0
        if not self.in_speech:
            self.preroll.append(frame)
            if not loud:
                self.noise = 0.95 * self.noise + 0.05 * rms
            self.run = self.run + 1 if loud else 0
            if self.run >= (BARGE_FRAMES if active else START_FRAMES):
                if active:
                    self.interrupt()
                elif self.holding and self.task:
                    self.task.cancel()   # user is continuing their sentence: drop the held reply
                self.in_speech, self.silence, self.voiced = True, 0, self.run
                self.buf = list(self.preroll)
        else:
            self.buf.append(frame)
            self.voiced += loud
            self.silence = 0 if loud else self.silence + 1
            if self.silence >= SILENCE_FRAMES:
                self.end_utterance()

    def interrupt(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.client_speaking = False
        self.turn_id += 1
        asyncio.get_running_loop().create_task(self.send({"type": "stop", "turn": self.turn_id}))

    def end_utterance(self):
        keep = self.buf[:len(self.buf) - max(0, self.silence - 5)]   # trim trailing quiet: less to upload
        pcm, voiced = b"".join(keep), self.voiced
        self.buf, self.in_speech, self.run, self.silence, self.voiced = [], False, 0, 0, 0
        self.preroll.clear()
        if voiced >= MIN_VOICED_FRAMES:
            self.task = asyncio.get_running_loop().create_task(self.turn(pcm, voiced))

    # ---- one conversational turn ----
    async def turn(self, pcm: bytes, voiced: int = 99):
        tid, reply = self.turn_id, ""
        t0 = time.monotonic()
        filler = asyncio.get_running_loop().create_task(self._filler(tid))
        try:
            text = await self.hear(pcm)
            word = text.lower().strip(" .,!?")
            if len(text) < 2 or (self.en and (word in HALLUCINATIONS or word in FILLER or (voiced < 25 and word in SHORT_NOISE))):
                log.info("ignored noise: %r", text)
                return
            mood = "neutral"
            try:   # voice sensing must never break a call
                feats = analyze(pcm)
                mood = self.baseline.mood(feats)
                if is_laughing(text):
                    mood = "laughing"
                elif text_mood(text):
                    mood = text_mood(text)       # what you said beats how loud you were
                self.profile.observe(text, mood)
                if feats:
                    log.info("voice: %s (pitch %.0f Hz, loudness %.3f, %.1f beats/s)", mood,
                             feats["pitch"], feats["loud"], feats["rate"])
            except Exception:
                log.exception("voice analysis failed")
            if self.pending and time.monotonic() - self.pending_t < 8:
                text = f"{self.pending} {text}"
            self.pending = ""
            if not text.rstrip().endswith(tuple('.?!"\'…')):
                # sounds unfinished: give the caller a moment to continue before answering
                self.pending, self.pending_t, self.holding = text, time.monotonic(), True
                try:
                    await asyncio.sleep(HOLD_SECONDS)
                finally:
                    self.holding = False
                self.pending = ""
            t_stt = time.monotonic() - t0
            log.info("user: %s  [stt %.1fs]", text, t_stt)
            self.history.append({"role": "user", "content": text})
            buf, first, n = "", False, 0
            natural = self.natural()
            spoken = []
            # keep the system prompt forever; only trim older chat turns
            note = REMINDER + (" " + DIRECTIONS if natural else "")
            felt = {"excited": "louder, higher and faster than usual (energetic)",
                    "low": "quieter and slower than usual (maybe tired or subdued)",
                    "laughing": "amused and laughing"}.get(mood)
            if felt:
                note += f" The caller sounds {felt}; match their mood" + (" with a fitting [direction]." if natural else ".")
            memory = self.profile.summary()
            if memory:
                note += " " + memory
            msgs = [self.history[0], *self.history[1:][-12:], {"role": "system", "content": note}]
            async with aclosing(self.groq.stream_chat(msgs)) as stream:
                async for tok in stream:
                    buf += tok
                    while (p := pop_sentence(buf)):
                        sent, buf, is_end = p
                        reply += sent
                        if not first and not natural:
                            filler.cancel()
                            first = True
                            log.info("first words ready %.1fs after you stopped talking", time.monotonic() - t0)
                        if natural:
                            spoken.append(clean(sent))
                        elif plain(sent):
                            await self.send({"type": "say", "turn": tid, "text": plain(sent)})
                        n += is_end
                    if n >= MAX_SENTENCES:
                        buf = ""
                        break
            if clean(buf):
                reply += buf
                if natural:
                    spoken.append(clean(buf))
                elif plain(buf):
                    await self.send({"type": "say", "turn": tid, "text": plain(buf)})
            filler.cancel()
            if natural and spoken:
                await self.speak_chunks(tid, spoken, t0)
            log.info("ai: %s", reply)
        except asyncio.CancelledError:
            raise
        except ServiceError as e:      # expected failures: the caller gets a friendly line, the owner gets the detail
            log.error("[%s] turn failed (%s): %s", self.ref, e.code, e.detail)
            await self.send({"type": "notice", "code": e.code})
        except Exception:
            log.exception("[%s] turn failed unexpectedly", self.ref)
            await self.send({"type": "notice", "code": "generic"})
        finally:
            filler.cancel()
            if reply:
                self.history.append({"role": "assistant", "content": reply})
