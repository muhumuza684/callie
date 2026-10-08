"""LLM fallback chain: free OpenAI-compatible providers tried in order, plus <think> stripping."""
import os

from server import config

PROVIDERS = {   # name -> (base url, env var holding the key)
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
}


def llm_chain():
    """[(provider, model, base_url, api_key)] from LLM_CHAIN='groq:model,cerebras:model'; entries without a key are skipped."""
    out = []
    for item in config.LLM_CHAIN.split(","):
        prov, _, model = item.strip().partition(":")
        if prov not in PROVIDERS or not model:
            continue
        base, env = PROVIDERS[prov]
        key = config.GROQ_API_KEY if prov == "groq" else os.getenv(env, "").strip()
        if key:
            out.append((prov, model, base, key))
    return out


class ThinkStripper:
    """Removes <think>...</think> blocks from a token stream (some reasoning models emit them in the text)."""

    def __init__(self):
        self.inside, self.buf = False, ""

    def feed(self, tok: str) -> str:
        self.buf += tok
        out = ""
        while True:
            if self.inside:
                i = self.buf.find("</think>")
                if i < 0:
                    self.buf = self.buf[-8:]
                    return out
                self.buf, self.inside = self.buf[i + 8:], False
            else:
                i = self.buf.find("<think>")
                if i < 0:
                    keep = max((k for k in range(1, min(7, len(self.buf) + 1)) if "<think>".startswith(self.buf[-k:])), default=0)
                    out += self.buf[:len(self.buf) - keep]
                    self.buf = self.buf[len(self.buf) - keep:]
                    return out
                out += self.buf[:i]
                self.buf, self.inside = self.buf[i + 7:], True

    def flush(self) -> str:
        return "" if self.inside else self.buf
