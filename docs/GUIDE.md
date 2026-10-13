# Callie guide

Callie lets you talk with friendly AI companions by voice, as simply as making a phone call.
This guide has two parts: **using Callie** (everyone) and **for developers** (the bottom).

## Install

| System | What to do |
|---|---|
| **Windows** | Download `Callie-windows.exe` from the [releases page](https://github.com/muhumuza684/callie/releases/latest), move it to your Desktop and double-click it. If Windows says *"Windows protected your PC"*, choose **More info**, then **Run anyway** (the app is new and not yet signed). |
| **Mac (Apple silicon)** | Download `Callie-macos.tar.gz`, double-click it to unpack, then right-click **Callie** and choose **Open** the first time. |
| **Linux** | Download `Callie-linux.tar.gz`, unpack it, run `chmod +x Callie`, then `./Callie`. |
| **Android and iPhone** | See [Use it on your phone](#use-it-on-your-phone). |

Callie opens in its own window. When you close the window, Callie quits by itself after a few minutes. Double-click it again whenever you want to talk.

## First run

The first time, Callie shows a short **Set up Callie** page. It needs a free access key to talk:

1. Open [console.groq.com/keys](https://console.groq.com/keys), sign in and create a key.
2. Paste it into the box and press **Save and start**.
3. The key is stored only on your computer, in Callie's own folder (see *Where your data lives*).

For the natural English voices, also accept the voice terms once at
[the voice page](https://console.groq.com/playground?model=canopylabs/orpheus-v1-english). Without it Callie still talks, using a simpler voice.

## Making a call

- Tap a contact. It rings, then answers with a short greeting that says it is an AI.
- Just talk. You can interrupt at any time. Use **Mute** to stop it hearing you and **End** to hang up.
- Use headphones for the best result: they stop the voice echoing back into your microphone.

## Contacts

Tap **+** to create a contact: a name, a voice and a language.

- **Voices:** female, male, girl, boy, baby, adult, old lady, old man, stranger. Girl, boy, baby and the old voices are adult voices shaped to sound younger or older, so they sound like characters. Child-style contacts always stay playful and age-appropriate.
- **Languages:** English, Kiswahili, Francais, Espanol, Arabic, Chinese, Hindi, Portuguese. Callie listens and answers in the contact's language. Natural voices are strongest in English; other languages use a voice installed on your device.
- **Edit** lets you delete contacts. Recents shows your calls, and tapping one calls back.

## Schedule

Open **Schedule**, tap **+**, choose a contact and a time. Every day at that time Callie rings you like an incoming call. For now this works while Callie is open and the sound is on.

## Settings

| Setting | What it does |
|---|---|
| Notifications | Lets Callie show a notice for an incoming scheduled call |
| Ringtone | Five built-in tones, or "Phone default" to use your phone's own sound and vibration |
| Theme | Auto, Midnight, Daylight, Ocean, Sunset, Royal |
| Microphone | Choose a microphone and press **Test** to check it. It listens only while the test runs |
| Remember conversations | Off by default. When on, Callie keeps short notes per contact so you can continue later. **Clear memories** deletes them |
| About, FAQ, Support | What Callie is for, five answered questions, and the support addresses with Copy and Write buttons |

## Use it on your phone

Callie is a web app, so a phone can use it without an app store. The phone needs a secure (https) address. A free tunnel gives your computer one:

- **From the source folder (Windows):** run `Callie.cmd`, choose **2**. It prints a link and opens a QR code. Scan it with your phone.
- **With the downloaded app:** install Cloudflare's free `cloudflared`, keep Callie open, and run `cloudflared tunnel --url http://127.0.0.1:8731`. It prints a link ending in `trycloudflare.com`.

Then open the link on your phone, allow the microphone and use headphones. Install it from the browser menu: **Install app** on Android Chrome, or **Share > Add to Home Screen** on iPhone Safari.

The link changes every time and works only while your computer and Callie are running. **Do not share it:** anyone who has it can use your Callie.

## Where your data lives

| System | Folder |
|---|---|
| Windows | `%APPDATA%\Callie` |
| Mac | `~/Library/Application Support/Callie` |
| Linux | `~/.local/share/Callie` |

It holds your key (`.env`), contacts and schedule (`data/store.json`), memory (`data/memory.json`) and a log file (`logs/callie.log`). Recordings of your voice are never saved. Deleting the folder removes everything.

## Troubleshooting

| What happens | What to do |
|---|---|
| Nobody hears me | Check your device's mute key, then open Settings > Microphone: press **Allow microphone** and **Test**. On a phone, make sure the browser is allowed to use the microphone (site settings) and that no other app is using it |
| "Your connection is weak" | Check your internet. If you use a VPN, switch it off and try again |
| Only a simple voice | Accept the voice terms (see First run), then restart Callie |
| A language has no voice | Install a voice for it in your system's speech settings |
| Scheduled call did not ring | Callie must be open with the sound on |
| Something else | Settings > Support, and quote the reference shown there |

## Privacy

Callie does not record or keep your calls. Your speech is processed only to understand you and to answer. Memory is off unless you switch it on. Callie always says it is an AI, can make mistakes, and is not a substitute for professional, medical or emergency help.

---

# For developers

## Run from source

Requirements: Python 3.10+ (developed on 3.14) and a free key.

```powershell
# Windows: double-click Callie.cmd, or
.\scripts\setup.ps1      # creates .venv, installs packages, runs tests, asks for the key
.\scripts\run.ps1        # starts http://127.0.0.1:8000
```

On Mac or Linux: `python3 -m venv .venv`, `.venv/bin/pip install -r requirements-base.txt -r requirements-dev.txt`, then `.venv/bin/python -m uvicorn server.main:app --port 8000`.

## Layout

```
client/pwa/     the app: index.html, app.js, style.css, setup.html, worklet.js, manifest, service worker, icons
desktop/main.py starts the server inside the app and opens its window
server/         main (API), ws (calls), groq (speech + AI + failover), llm, store, memory, config
pipeline/       one call: turn-taking, listening, reply, memory, voice sensing
audio/          audio helpers (pcm, voice_features)
conversation/   local topic and mood profile
scripts/        launcher and helpers
tests/          automated tests
docs/           landing page (GitHub Pages) and this guide
```

## Configuration (`.env` in the data folder)

| Setting | Default | Meaning |
|---|---|---|
| `GROQ_API_KEY` | none | the access key (required) |
| `LLM_CHAIN` | three models, in order | models tried in turn; add `cerebras:`, `openrouter:` or `mistral:` entries with their keys for more fallback |
| `GROQ_STT_MODEL` | `whisper-large-v3-turbo` | speech recognition |
| `STT_LANGUAGE`, `STT_HINT` | `en`, names and terms | default language and spelling hints (English) |
| `TTS_MODE` | `orpheus` | `orpheus` natural English voice, `browser` basic voice |
| `VOICE_FEMALE`, `VOICE_MALE`, ... | built-in | which voice each type uses |
| `SUPPORT_EMAILS` | the two support addresses | shown in Settings > Support |
| `CALLIE_HOME`, `CALLIE_PORT` | per system, `8731` (app) | data folder and port |

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```

The tests also check that every button has a handler, that nothing technical is shown to users, and that the docs and release links agree.

## Build and release

- **On GitHub (recommended):** the launcher's option **6** (or `.\scripts\release.ps1`) tags the number in `VERSION` and pushes the tag. The workflow in `.github/workflows/build.yml` runs the tests, builds the Windows, Mac and Linux apps and attaches them to a Release. Raise `VERSION` for each new release.
- **On your PC:** `.\scripts\build-exe.ps1` builds `Callie.exe` and copies it to your Desktop.
- **Move to the desktop app:** `.\scripts\migrate-to-app.ps1` copies your key, contacts and memory into the app's folder.

## Keeping the repository clean

`.gitignore` keeps keys, personal data, build output and tools out of git. `scripts/stale.txt` lists files that are no longer used, and the launcher deletes them after an update. `.\scripts\clean.ps1` frees disk space without touching your key or data.
