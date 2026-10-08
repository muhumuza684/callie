"""VAD. EnergyVAD works with zero dependencies; swap for Silero later
(same is_speech(float32 frame) interface)."""
import numpy as np


class EnergyVAD:
    def __init__(self, threshold: float = 0.015, hangover_frames: int = 10):
        self.threshold = threshold
        self.hangover = hangover_frames
        self._left = 0

    def is_speech(self, frame: np.ndarray) -> bool:
        rms = float(np.sqrt(np.mean(frame ** 2))) if len(frame) else 0.0
        if rms > self.threshold:
            self._left = self.hangover
            return True
        if self._left > 0:
            self._left -= 1
            return True
        return False
