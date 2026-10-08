import numpy as np

from audio.pcm import float_to_pcm16
from audio.voice_features import Baseline, analyze
from conversation.profile import Profile, is_laughing


def voice(f0, amp, secs=1.2, beats=4):
    """Fourier-series 'vowel': harmonics of f0, with a syllable-like amplitude rhythm."""
    t = np.arange(int(16000 * secs)) / 16000
    sig = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 8))
    env = 0.5 + 0.5 * np.sin(2 * np.pi * beats * t) ** 2
    return float_to_pcm16((amp * sig * env / 2).astype("f4"))


def test_pitch_found():
    f = analyze(voice(200, 0.4))
    assert f and abs(f["pitch"] - 200) < 8


def test_mood_relative_to_own_baseline():
    b = Baseline()
    for _ in range(4):
        assert b.mood(analyze(voice(150, 0.2))) == "neutral"
    assert b.mood(analyze(voice(230, 0.5, beats=6))) == "excited"
    assert b.mood(analyze(voice(120, 0.05, beats=2))) == "low"


def test_silence_is_none():
    assert analyze(b"\0" * 32000) is None


def test_profile_counts_and_markov(tmp_path):
    p = Profile(tmp_path / "p.json")
    for _ in range(3):
        p.observe("I love jazz music", "neutral")
        p.observe("help with my python code", "neutral")
    s = p.summary()
    assert "music" in s and "jazz" in s
    assert Profile.likely(p.topic_next, "music") == "tech"
    assert Profile(tmp_path / "p.json").genres["jazz"] == 3     # persisted
    assert "love" not in (tmp_path / "p.json").read_text()      # counts only, not your words


def test_laugh_text():
    assert is_laughing("ha ha ha that was funny") and is_laughing("haha good one")
    assert not is_laughing("have a nice day") and not is_laughing("what a hat")


def test_text_beats_voice_for_mood():
    from conversation.profile import text_mood
    assert text_mood("You know what? I feel tired.") == "low" and text_mood("what is python") is None
