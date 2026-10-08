# Callie

**Call an AI by voice, like phoning a friend.** Callie is a voice-first web app (PWA): tap a contact, hear it ring, and just talk. Each contact has its own name, voice type, language and (optionally) memory. It runs on your own computer, uses free-tier cloud AI, and can be opened from your phone through a free secure link.

> Built in Uganda, by **Bryt Ma Tech UG**.

---

## Features

- **Phone-style calling** - green call screen, ringing, timer, mute, hang up, recents, and scheduled calls that ring in the app.
- **Real conversation** - turn-taking by voice activity, interruptions (barge-in), waits a moment when you pause mid-sentence, and says "one moment" when the network is slow.
- **Contacts with personalities** - create people with a name, a voice type (Female, Male, Girl, Boy, Baby, Adult, Old lady, Old man, Stranger) and a language.
- **8 languages** - English, Kiswahili, Francais, Espanol, Arabic, Chinese, Hindi, Portugues. Listening and replies work in all of them.
- **Natural English voice** - Groq's Orpheus voices with mood tags; other languages use a voice installed on the device.
- **Model fallback** - if one AI model is down or rate-limited, the next one answers (`LLM_CHAIN`).
- **Voice sensing** - compares pitch, loudness and rhythm with your own average (Fourier-based) to notice when you sound more or less energetic.
- **Optional memory** - off by default; when on, Callie keeps short notes per contact so you can continue conversations (Settings).
- **Themes and ringtones** - six looks (Auto, Midnight, Daylight, Ocean, Sunset, Royal) and five built-in ringtones, or the phone's own notification sound (Settings).
- **Installable** - works as an app on Android and iPhone; one-click launcher on Windows.
- **Safety basics** - every greeting says it is an AI, an "AI" badge on the call screen, self-harm replies point to help, child-style voices stay age-appropriate.

## How it works

```
 Browser / phone (PWA)                          Your PC (FastAPI server)
 ---------------------                          -------------------------------------------
 microphone  -> 16 kHz audio frames --WebSocket-->  voice activity detection (turn-taking)
                                                    -> Groq Whisper        (speech to text, ~99 languages)
                                                    -> LLM chain           (Groq gpt-oss / Qwen3, optional Cerebras ...)
 speaker  <- audio (Orpheus) or text --WebSocket--  -> Groq Orpheus voice   (English) or browser voice
 contacts, recents, schedule  <-- REST /api -->     JSON store (data/store.json), optional memory.json
```

## Requirements

- Windows 10/11 with **Python 3.10+** (python.org, tick "Add to PATH"). Developed on Python 3.14.
- A free **Groq API key** - https://console.groq.com/keys
- Accept the voice terms once: https://console.groq.com/playground?model=canopylabs/orpheus-v1-english
- A microphone, and headphones for the best experience.

## Quick start (Windows)

1. Download or clone this repo.
2. Double-click **`Callie.cmd`** (or run `.\scripts\make-shortcut.ps1` once for a Desktop icon).
3. First run: it creates the Python environment, installs packages and asks for your Groq key.
4. Choose **1** to start on this PC. The browser opens; allow the microphone and tap a contact.

Manual start: `.\scripts\setup.ps1` then `.\scripts\run.ps1`.

**Updating:** download a newer `voice-ai-pwa-vNN.zip` into Downloads and start Callie - it offers to apply it and keeps your `.env`, contacts and memory.

## Use it on your phone

1. Start Callie, then choose **2** in the launcher (or run `.\scripts\phone.ps1`).
2. First time it downloads the free Cloudflare tunnel tool (about 40 MB), then prints an https link and opens a QR code.
3. Scan it, allow the microphone, use headphones. Android Chrome: menu > Install app. iPhone Safari: Share > Add to Home Screen.

The link changes every time and works only while your PC, Callie and the script are running. Do not share it: anyone with it can use your Groq quota and see your contacts.

## Configuration (`.env`)

| Setting | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | - | Your free Groq key (required) |
| `LLM_CHAIN` | `groq:<GROQ_LLM_MODEL>,groq:openai/gpt-oss-120b,groq:qwen/qwen3-32b` | Models tried in order; add `cerebras:`, `openrouter:`, `mistral:` entries with their keys |
| `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY` | - | Optional extra providers for fallback |
| `GROQ_STT_MODEL` | `whisper-large-v3-turbo` | Speech recognition model |
| `STT_LANGUAGE` | `en` | Language for contacts without their own |
| `STT_HINT` | names and tech terms | Spelling hints for English listening |
| `TTS_MODE` | `orpheus` | `orpheus` = natural English voice, `browser` = instant basic voice |
| `VOICE_FEMALE`, `VOICE_MALE`, `VOICE_GIRL` ... | autumn / diana / daniel ... | Which Orpheus voice each type uses (autumn, diana, hannah, austin, daniel, troy) |
| `GREETING`, `SYSTEM_PROMPT` | built in | Default greeting and personality |

## Voices and languages

- Orpheus has six English voices (3 female, 3 male). Girl, Boy, Baby and the Old types are those voices pitch- and speed-shaped, so they sound like characters, not real children or elders.
- Orpheus is English-only here. Other languages use a voice installed on your device (Windows Settings > Time & language > Speech).
- Custom (cloned) voices are not built. See the roadmap for the consent-first plan.

## Memory and privacy

- **Memory is off by default.** Turn it on in **Settings > Remember conversations**. Callie then keeps a short summary and the last messages per contact in `data/memory.json` on your computer. **Clear memories** deletes it; deleting a contact deletes its memory.
- Audio is not recorded or stored. It is streamed to Groq for transcription and the reply, and discarded.
- Groq does not retain inference data by default and offers Zero Data Retention in its console. Retained logs, if any, are stored in the US. Name Groq in any privacy notice you publish.
- `.env`, `data/*.json` and `tools/` are git-ignored. Never commit your key.

## Project structure

```
Callie.cmd              one-click launcher
VERSION                 current version number
client/pwa/             the app (index.html, app.js, style.css, worklet.js, manifest, icons)
server/                 FastAPI app, WebSocket, Groq + LLM chain, store, memory, config
pipeline/runner.py      call session: turn-taking, speech to reply, memory, voice sensing
audio/  vad/            audio helpers, Fourier analysis, voice detection
conversation/           local topic/mood profile
scripts/                setup, run, phone, push, launcher, shortcut, diagnostics
tests/                  automated tests (pytest)
```

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests --ignore=tests/test_audio.py
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Nobody hears me (`mic: peak 0.000` in the log) | Microphone muted - press the laptop mic-mute key (F4 on many Lenovos), or pick another mic in **Settings > Microphone** and watch the level bar |
| "Can't reach Groq" | Turn off any VPN, check your internet; `.\scripts\check-groq.ps1` diagnoses it |
| Only the basic voice | Accept the Orpheus terms (link above) and restart Callie |
| Page looks unstyled after an update | Press Ctrl+F5 |
| No voice for a language | Install a voice in Windows Settings > Time & language > Speech |
| Scheduled call did not ring | Scheduled calls ring only while the Callie page is open (push notifications are on the roadmap) |
| A Settings button does nothing | Press Ctrl+F5 to load the newest page; if it still fails, send the PowerShell log |
| Port 8000 already in use | Close the other Callie window, or run only one copy |

## Errors, support and what people can see

- People only ever see calm, plain messages ("Your connection is weak. Please try again in a moment."). Technical detail never reaches the screen.
- The owners get the detail in `logs/callie.log` (rotating). Each device has a short support reference (shown only in the "Report a problem" email), so a message from a user can be matched to the log.
- **Settings > Support** is one button: it opens a panel with the support addresses (set with `SUPPORT_EMAILS` in `.env`), each with Copy and Write. Write opens webmail on computers and the email app on phones, with the support reference already filled in. Settings also holds About Callie and a five-question FAQ.
- The server publishes no API documentation, `/health` says only "ok", and invalid or failing requests return a generic answer.
- A web page's own code can always be read in a browser. Anything sensitive (keys, prompts, models, rules) stays on the server.

## Security notes

Callie has no login. It is meant for one person on their own PC. If you expose it with the phone link, treat the link like a password. Before offering it to other people it needs accounts, rate limits and a consent screen (see roadmap).

## Platforms
- **Everywhere:** Callie is a PWA, so one codebase runs on Android, iPhone, Windows, Mac and Linux. On computers the app fills the window like WhatsApp Web (contacts on the left, the call on the right).
- **Planned:** host the server so people need nothing installed; thin desktop apps (Windows `.exe`, Mac, Linux) that open the hosted app; store apps for Android and iOS.

## Roadmap

1. Push notifications so scheduled calls ring when the phone screen is off.
2. First-run privacy and consent screen; Zero Data Retention switched on.
3. Text/transcript option for accessibility.
4. Accounts, rate limits, delete-my-data, and an always-on server.
5. Offline fallback on the PC (Whisper/SenseVoice listening, Kokoro speaking).
6. Custom voices recorded with the speaker's explicit, recorded consent.
7. Native Android app for a true locked-screen incoming call.

## Standards and compliance notes

Not legal advice. Relevant areas for a public launch: Uganda's Data Protection and Privacy Act 2019 (registration and consent), GDPR and the EU AI Act (AI disclosure and labelling of synthetic audio), California's companion-chatbot law, COPPA for children's data, OWASP guidance for LLM apps, and WCAG for accessibility.

## License

All rights reserved by Bryt Ma Tech UG until a license is chosen.
