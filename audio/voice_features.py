"""Voice analysis with Fourier tools: pitch (FFT autocorrelation), loudness, speaking rate.
We compare each utterance with the caller's OWN recent average, so 'excited' means
louder/higher/faster than usual for them. It senses energy, not true emotion."""
import numpy as np

from audio.pcm import SAMPLE_RATE, pcm16_to_float

FRAME, HOP = 640, 320          # 40 ms windows, 20 ms hop


def _pitch(frame: np.ndarray):
    f = frame - frame.mean()
    n = len(f)
    spec = np.fft.rfft(f, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]          # autocorrelation via the Fourier transform
    ac = ac / (ac[0] + 1e-9)
    lo, hi = SAMPLE_RATE // 400, SAMPLE_RATE // 70       # 70-400 Hz = human voice
    seg = ac[lo:hi]
    k = int(seg.argmax())
    return SAMPLE_RATE / (lo + k) if seg[k] > 0.35 else None


def analyze(pcm: bytes):
    x = pcm16_to_float(pcm)
    if len(x) < FRAME * 5:
        return None
    n = (len(x) - FRAME) // HOP + 1
    frames = np.stack([x[i * HOP:i * HOP + FRAME] for i in range(n)])
    rms = np.sqrt((frames ** 2).mean(axis=1))
    voiced = rms > max(0.01, 0.35 * np.percentile(rms, 90))
    if voiced.sum() < 8:
        return None
    pitches = [p for p in (_pitch(f) for f in frames[voiced]) if p]
    pitch = float(np.median(pitches)) if len(pitches) >= 5 else 0.0
    sm = np.convolve(rms, np.ones(3) / 3, mode="same")
    peaks = int(((sm[1:-1] > sm[:-2]) & (sm[1:-1] >= sm[2:]) & (sm[1:-1] > 0.5 * np.percentile(sm, 90))).sum())
    return {"loud": float(rms[voiced].mean()), "pitch": pitch, "rate": peaks / (len(x) / SAMPLE_RATE)}


class Baseline:
    """Running average of this caller's voice; returns 'excited', 'low' or 'neutral'."""

    def __init__(self):
        self.n, self.v = 0, {"loud": 0.0, "pitch": 0.0, "rate": 0.0}

    def mood(self, f) -> str:
        if not f:
            return "neutral"
        label = "neutral"
        if self.n >= 3:
            b = self.v
            arousal = 0.5 * (f["loud"] / b["loud"] - 1)
            if f["pitch"] and b["pitch"]:
                arousal += 0.3 * (f["pitch"] / b["pitch"] - 1)
            if b["rate"]:
                arousal += 0.2 * (f["rate"] / b["rate"] - 1)
            label = "excited" if arousal > 0.3 else "low" if arousal < -0.3 else "neutral"
        for k in self.v:
            if f[k]:
                self.v[k] = f[k] if self.n == 0 or not self.v[k] else 0.8 * self.v[k] + 0.2 * f[k]
        self.n += 1
        return label
