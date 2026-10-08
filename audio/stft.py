"""Fourier / STFT tools: analysis + spectral-gating noise reduction."""
import numpy as np
from scipy.signal import stft, istft

from audio.pcm import SAMPLE_RATE


def spectrogram(x: np.ndarray, fs: int = SAMPLE_RATE, nperseg: int = 512):
    f, t, Z = stft(x, fs=fs, nperseg=nperseg)
    return f, t, np.abs(Z)


def dominant_frequency(x: np.ndarray, fs: int = SAMPLE_RATE) -> float:
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.fft.rfftfreq(len(x), 1 / fs)[spec.argmax()])


def spectral_gate(x: np.ndarray, fs: int = SAMPLE_RATE, noise_seconds: float = 0.3,
                  threshold: float = 1.5, nperseg: int = 512) -> np.ndarray:
    """Estimate noise floor from the first `noise_seconds` (assumed silence),
    then zero STFT bins below threshold * noise. Offline version for the lab."""
    f, t, Z = stft(x, fs=fs, nperseg=nperseg)
    mag = np.abs(Z)
    n = max(1, int(noise_seconds * fs / (nperseg // 2)))
    noise = mag[:, :n].mean(axis=1, keepdims=True)
    mask = (mag > threshold * noise).astype(np.float32)
    _, y = istft(Z * mask, fs=fs, nperseg=nperseg)
    return y[: len(x)].astype(np.float32)
