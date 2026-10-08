"""Connectivity check from Python (same stack the server uses)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx

from server import config

print("key set:", bool(config.GROQ_API_KEY))
for i in range(3):
    t = time.time()
    try:
        r = httpx.get("https://api.groq.com/openai/v1/models",
                      headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"}, timeout=45)
        print(f"try {i+1}: HTTP {r.status_code} in {time.time()-t:.1f}s")
        break
    except Exception as e:
        print(f"try {i+1}: FAILED after {time.time()-t:.1f}s -> {type(e).__name__}")
