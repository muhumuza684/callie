"""Audio laboratory (M1).
  python -m audio.lab record 5          -> data/recordings/raw.wav
  python -m audio.lab clean             -> data/recordings/clean.wav
  python -m audio.lab analyze           -> prints dominant freq, RMS, speech %
Requires requirements-audio.txt."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from audio.pcm import SAMPLE_RATE
from audio.stft import dominant_frequency, spectral_gate
from vad.detector import EnergyVAD

REC = Path("data/recordings")


def record(seconds: float):
    import sounddevice as sd
    print(f"Recording {seconds}s - stay quiet for the first 0.3s, then speak...")
    x = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    REC.mkdir(parents=True, exist_ok=True)
    sf.write(REC / "raw.wav", x[:, 0], SAMPLE_RATE)
    print("saved", REC / "raw.wav")


def clean():
    x, _ = sf.read(REC / "raw.wav", dtype="float32")
    sf.write(REC / "clean.wav", spectral_gate(x), SAMPLE_RATE)
    print("saved", REC / "clean.wav")


def analyze():
    for name in ("raw", "clean"):
        p = REC / f"{name}.wav"
        if not p.exists():
            continue
        x, _ = sf.read(p, dtype="float32")
        vad, hop, hits = EnergyVAD(), 320, 0
        frames = range(0, len(x) - hop, hop)
        for i in frames:
            hits += vad.is_speech(x[i:i + hop])
        print(f"{name}: rms={np.sqrt((x**2).mean()):.4f} dominant={dominant_frequency(x[:SAMPLE_RATE]):.0f}Hz speech={100*hits/max(1,len(frames)):.0f}%")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    {"record": lambda: record(float(sys.argv[2]) if len(sys.argv) > 2 else 5), "clean": clean, "analyze": analyze}[cmd]()
