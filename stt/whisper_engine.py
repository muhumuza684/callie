"""STT stub (M2). pip install faster-whisper, then implement transcribe()."""
class WhisperEngine:
    def __init__(self, model_size: str = "tiny.en"):
        from faster_whisper import WhisperModel  # lazy import
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_f32, sample_rate: int = 16000) -> str:
        segments, _ = self.model.transcribe(audio_f32, language="en")
        return " ".join(s.text.strip() for s in segments)
