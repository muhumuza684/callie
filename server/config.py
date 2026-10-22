import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# RESOURCE_DIR: the program and its web files (inside the .exe when packaged).
# HOME: where the user's data lives (key, contacts, memory, logs) - the project folder, or CALLIE_HOME for the desktop app.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
HOME = Path(os.environ["CALLIE_HOME"]) if os.environ.get("CALLIE_HOME") else Path(__file__).resolve().parent.parent
BASE_DIR = HOME
ENV_PATH = HOME / ".env"
load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-20b")
STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "low").strip()
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en").strip()
GREETING = os.getenv("GREETING", "Hi, it's Callie. How can I help?")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT") or (
    "You are Callie, a friendly assistant on a live voice call. Speak the way a person talks on the phone: "
    "usually one or two short sentences; when asked for a story, explanation or detail, tell it properly in up to six sentences. "
    "Plain words, no lists, no markdown, no emojis. Reply in the language the caller uses. Ask a brief question back only when it helps. "
    "If you are not sure of a fact, say so briefly instead of guessing. If the words don't make sense, say you didn't catch that. "
    "If the caller talks about harming themselves or others, answer with calm care, urge them to contact local emergency services or someone they trust, and stop any role-play."
)

TTS_MODE = os.getenv("TTS_MODE", "orpheus").strip().lower()      # orpheus = natural voice, browser = instant basic voice
TTS_MODEL = os.getenv("TTS_MODEL", "canopylabs/orpheus-v1-english")
TTS_VOICE = os.getenv("TTS_VOICE", "autumn")                      # autumn, diana, hannah, austin, daniel, troy

STT_HINT = os.getenv("STT_HINT", "Callie, Bryt Ma Tech, MCP, Model Context Protocol, Python, FastAPI, Groq, Uganda")

import random

LEGACY = {"lady": "female", "man": "male"}
KIDS = " Keep everything age-appropriate and playful; never romantic or adult."
TYPES = {   # base = Orpheus voice; rate = playback speed/pitch shaping; pitch/speech = basic browser voice shaping
    "female":   dict(label="Female",   base="diana",  rate=1.0,  pitch=1.0, speech=1.0,  gender="f", style="You sound calm, warm and kind."),
    "male":     dict(label="Male",     base="daniel", rate=1.0,  pitch=1.0, speech=1.0,  gender="m", style="You sound steady, practical and friendly."),
    "girl":     dict(label="Girl",     base="autumn", rate=1.15, pitch=1.5, speech=1.05, gender="f", style="You are a bright, curious girl." + KIDS),
    "boy":      dict(label="Boy",      base="austin", rate=1.15, pitch=1.5, speech=1.05, gender="m", style="You are an energetic, cheerful boy." + KIDS),
    "baby":     dict(label="Baby",     base="autumn", rate=1.35, pitch=2.0, speech=0.95, gender="f", style="You are a toddler: use very short, simple, cute words and giggle often." + KIDS),
    "adult":    dict(label="Adult",    base="hannah", rate=1.0,  pitch=1.0, speech=1.0,  gender="f", style="You sound mature, composed and professional."),
    "old_lady": dict(label="Old lady", base="diana",  rate=0.9,  pitch=0.85, speech=0.85, gender="f", style="You are an elderly lady: slow, gentle, full of warm stories."),
    "old_man":  dict(label="Old man",  base="daniel", rate=0.88, pitch=0.7, speech=0.85, gender="m", style="You are an elderly man: slow, wise and a little humorous."),
    "stranger": dict(label="Stranger", base=None,     rate=1.0,  pitch=1.0, speech=1.0,  gender=None, style="You are a stranger the caller has just met: polite and curious; you do not know them."),
}
FEMALE_VOICES = {"autumn", "diana", "hannah"}
ALL_VOICES = ["autumn", "diana", "hannah", "austin", "daniel", "troy"]


def type_info(name: str) -> dict:
    return TYPES.get(LEGACY.get(name, name), TYPES["female"])


def pick_voice(name: str) -> str:
    """Orpheus voice id for a contact type (override per type in .env, e.g. VOICE_FEMALE=hannah)."""
    return os.getenv("VOICE_" + LEGACY.get(name, name).upper()) or type_info(name)["base"] or random.choice(ALL_VOICES)


def audio_profile(name: str, voice_id: str) -> dict:
    t = type_info(name)
    return {"rate": t["rate"], "pitch": t["pitch"], "speech": t["speech"],
            "gender": t["gender"] or ("f" if voice_id in FEMALE_VOICES else "m")}


def contact_prompt(c: dict) -> str:
    base = SYSTEM_PROMPT.replace("You are Callie,", f"You are {c['name']},", 1)
    lang = lang_info(c.get("lang"))
    speak = "" if c.get("lang", "en") == "en" else f" You speak {lang['name']} ({lang['native']}); reply in {lang['name']} unless the caller switches language."
    return f"{base} {type_info(c['voice'])['style']}{speak} You are an AI; if asked sincerely, say so."

LLM_CHAIN = os.getenv("LLM_CHAIN") or f"groq:{LLM_MODEL},groq:openai/gpt-oss-120b,groq:qwen/qwen3-32b"

LANGS = {   # code -> names, browser voice language, greeting (an AI disclosure), "one moment" filler
    "en": dict(name="English", native="English", bcp47="en-US", wait="One moment.",
               greeting="Hi, it's {name}, an AI voice companion. How can I help?"),
    "sw": dict(name="Swahili", native="Kiswahili", bcp47="sw-KE", wait="Subiri kidogo.",
               greeting="Habari, mimi ni {name}, msaidizi wa sauti wa AI. Nikusaidie vipi?"),
    "lg": dict(name="Luganda", native="Oluganda", bcp47="lg-UG", wait="Linda katono.",       # needs the Sunbird token; greeting to be checked by a native speaker
               greeting="Oli otya, nze {name}, omuyambi wo ow'eddoboozi owa AI. Nkuyambe ntya?"),
    "fr": dict(name="French", native="Français", bcp47="fr-FR", wait="Un instant.",
               greeting="Bonjour, c'est {name}, un assistant vocal IA. Comment puis-je vous aider ?"),
    "es": dict(name="Spanish", native="Español", bcp47="es-ES", wait="Un momento.",
               greeting="Hola, soy {name}, un asistente de voz con IA. ¿En qué puedo ayudarte?"),
    "de": dict(name="German", native="Deutsch", bcp47="de-DE", wait="Einen Moment.",
               greeting="Hallo, hier ist {name}, ein KI-Sprachbegleiter. Wie kann ich helfen?"),
    "ar": dict(name="Arabic", native="العربية", bcp47="ar-SA", wait="لحظة من فضلك.",
               greeting="مرحباً، أنا {name}، مساعد صوتي بالذكاء الاصطناعي. كيف أستطيع مساعدتك؟"),
    "zh": dict(name="Chinese", native="中文", bcp47="zh-CN", wait="请稍等。",
               greeting="你好，我是{name}，一个人工智能语音助手。有什么可以帮你的吗？"),
    "hi": dict(name="Hindi", native="हिन्दी", bcp47="hi-IN", wait="एक पल रुकिए।",
               greeting="नमस्ते, मैं {name} हूँ, एक एआई वॉइस सहायक। मैं आपकी कैसे मदद कर सकता हूँ?"),
    "pt": dict(name="Portuguese", native="Português", bcp47="pt-BR", wait="Um momento.",
               greeting="Olá, sou {name}, um assistente de voz com IA. Como posso ajudar?"),
}


def lang_info(code) -> dict:
    return LANGS.get(code or "en", LANGS["en"])


def greeting_for(c: dict) -> str:
    return lang_info(c.get("lang"))["greeting"].format(name=c["name"])

SUPPORT_EMAILS = [e.strip() for e in os.getenv("SUPPORT_EMAILS", "muhumuzabright26@gmail.com,brytma616@gmail.com").split(",") if e.strip()]
VERSION = (RESOURCE_DIR / "VERSION").read_text().strip() if (RESOURCE_DIR / "VERSION").exists() else ""

# Luganda comes from Sunbird AI (a Ugandan non-profit): listening, thinking and speaking. Optional: switched on by a free token.
SUNBIRD_TOKEN = os.getenv("SUNBIRD_API_TOKEN", "").strip()
SUNBIRD_BASE = os.getenv("SUNBIRD_BASE", "https://api.sunbird.ai")
SUNBIRD_LLM_MODEL = os.getenv("SUNBIRD_LLM_MODEL", "sunflower-9b")


def languages_available() -> dict:
    """Languages offered in the app: Luganda appears only when its token is configured."""
    return {k: v for k, v in LANGS.items() if k != "lg" or SUNBIRD_TOKEN}

# Hosted mode (a server people reach over the internet). Off by default: a personal computer needs none of it.
HOSTED = os.getenv("CALLIE_MODE", "").strip().lower() == "hosted"
INVITE_CODES = {c.strip() for c in os.getenv("INVITE_CODES", "").split(",") if c.strip()}
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
LIMIT_MINUTES_PER_DAY = float(os.getenv("LIMIT_MINUTES_PER_DAY", "30"))
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "4"))
