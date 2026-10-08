"""LLM stub (M2). Needs Ollama running locally: `ollama pull llama3.2:1b`."""
class OllamaEngine:
    def __init__(self, model: str = "llama3.2:1b"):
        self.model = model
        self.history = [{"role": "system", "content": "You are a friendly voice assistant. Reply in one or two short spoken sentences."}]

    def reply(self, text: str) -> str:
        import ollama
        self.history.append({"role": "user", "content": text})
        out = ollama.chat(model=self.model, messages=self.history)["message"]["content"]
        self.history.append({"role": "assistant", "content": out})
        return out
