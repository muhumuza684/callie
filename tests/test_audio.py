import numpy as np

from audio.stft import dominant_frequency, spectral_gate
from vad.detector import EnergyVAD


def test_dominant_frequency():
    t = np.arange(16000) / 16000
    assert abs(dominant_frequency(np.sin(2 * np.pi * 440 * t).astype("f4")) - 440) < 5


def test_spectral_gate_reduces_noise():
    rng = np.random.default_rng(0)
    t = np.arange(32000) / 16000
    sig = np.where(t > 0.5, 0.5 * np.sin(2 * np.pi * 300 * t), 0).astype("f4")
    noisy = sig + 0.02 * rng.standard_normal(len(t)).astype("f4")
    clean = spectral_gate(noisy)
    assert np.abs(clean[:4000]).mean() < np.abs(noisy[:4000]).mean()


def test_vad():
    v = EnergyVAD()
    assert not v.is_speech(np.zeros(320, "f4"))
    assert v.is_speech(np.full(320, 0.3, "f4"))
