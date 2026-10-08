"""TTS stub (M2). Piper needs a downloaded .onnx voice model in ./models."""
class PiperEngine:
    def __init__(self, model_path: str = "models/en_US-lessac-medium.onnx"):
        self.model_path = model_path

    def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("Install piper-tts, download a voice, then implement (returns PCM16 16 kHz).")
