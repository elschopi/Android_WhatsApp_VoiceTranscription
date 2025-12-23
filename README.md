# WhatsApp Voice Transcription (Android / Termux)

A small self-hosted tool to browse and transcribe your WhatsApp voice notes directly on your Android phone using Termux, a local Flask server, and a simple web UI.

- No WhatsApp modification / root required
- Reads your existing `.opus` voice notes from WhatsApp's media folder
- Transcription providers:
  - **Groq Whisper API** (online, fast, good accuracy)
  - **Local `whisper.cpp`** (offline, best for German, slower)
  - **Google Gemini** (online, via Generative Language API)
- Web UI with English / German language support
- Optional Termux widget scripts to quickly start/stop the transcriber

> **Privacy note:**  
> The script never uploads your WhatsApp audio files to GitHub. They are only read from local storage on your device.  
> API keys and other secrets are **not** stored in this repository and must be provided via environment variables on your own device.

---

## How it works

1. **Storage access:**  
   The Flask app runs in Termux on your Android device and scans your WhatsApp voice notes directory, for example:

   - `~/storage/shared/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes`
   - or `~/storage/shared/WhatsApp/Media/WhatsApp Voice Notes`

2. **Web UI:**  
   Opening `http://127.0.0.1:5000` in a browser on your phone shows a Tailwind-based interface where you:

   - Press **“Nachrichten suchen / Find Messages”** to load recent voice messages  
   - Select messages (or all)  
   - Choose transcription provider: **Groq**, **Local Whisper**, or **Gemini**  
   - Start transcription and see results inline per message (and in a log panel)

3. **Transcription providers:**
   - **Groq Whisper**: remote API (`whisper-large-v3`) with good speed and accuracy.
   - **Local whisper.cpp**: uses `whisper-cli` binary and a local `ggml-large-v3.bin` model.
     - Optimized in this project for **German** voice notes; language is forced to `de` by default.
   - **Gemini**: Google Generative Language API, used with a prompt to get pure text transcriptions.

4. **Database caching:**
   - A small SQLite database (`transcripts.db`) stores transcriptions keyed by file path.
   - Already transcribed messages are displayed as "transcribed" cards with cached text and no re-API calls.

---

## Requirements

- **Android phone** with WhatsApp installed
- **Termux** app (from F-Droid or the official source)
- Termux storage permission (`termux-setup-storage`)
- **Python 3** in Termux
- **ffmpeg** (for audio conversion when using `whisper.cpp`)
- Optionally:
  - `whisper.cpp` built on the device (for offline transcription)
  - Valid **Groq API key** (for remote Whisper)
  - Valid **Google Gemini API key**

---

## Installation (Termux / Android)

### 1. Install Termux and grant storage

1. Install **Termux** from F-Droid or the official source (not from random Play Store clones).
2. Open Termux and run:

   ```bash
   termux-setup-storage
   ```

   Confirm the permission dialog so Termux can read your WhatsApp media folders.

3. Update base packages:

   ```bash
   pkg update && pkg upgrade
   ```

### 2. Install Python and dependencies

In Termux:

```bash
pkg install python git ffmpeg
```

Clone the repository:

```bash
cd ~
git clone https://github.com/elschopi/Android_WhatsApp_VoiceTranscription.git
cd Android_WhatsApp_VoiceTranscription
```

Create and activate an (optional but recommended) virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install Python dependencies (Flask and requests are needed):

```bash
pip install flask requests
```

> Note: If you add a `requirements.txt` later, you can simply run:
> ```bash
> pip install -r requirements.txt
> ```

---

## Configuring transcription providers

The Flask app uses environment variables to configure providers. **Do not hard-code keys into the repo.**

### Environment variables

Set these in Termux (temporarily for the current session):

```bash
export GROQ_API_KEY="your-groq-api-key-here"
export GEMINI_API_KEY="your-gemini-api-key-here"
export WHISPER_CPP_DIR="$HOME/whisper.cpp/build/bin"
export WHISPER_CPP_MODEL="$HOME/whisper.cpp/models/ggml-large-v3.bin"
```

To make them persistent, add them to your `~/.bashrc` or `~/.zshrc` in Termux (but **never** commit those files to GitHub).

#### Groq Whisper

- `GROQ_API_KEY` – your Groq API key
- Uses endpoint:
  - `https://api.groq.com/openai/v1/audio/transcriptions`
- Model:
  - `whisper-large-v3`

If `GROQ_API_KEY` is not set, the **Groq** provider will be shown as unavailable in the UI.

#### Gemini

- `GEMINI_API_KEY` – your Gemini (Google Generative Language) API key
- Uses model:
  - `gemini-2.5-flash-preview-09-2025`  
    (via `generateContent` endpoint)

If `GEMINI_API_KEY` is not set, **Gemini** will be unavailable in the UI.

#### Local whisper.cpp

For offline transcription, compile and configure `whisper.cpp`:

```bash
cd ~
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
bash ./models/download-ggml-model.sh large-v3
mkdir -p build
cd build
cmake ..
make
```

Then set environment variables (adjust paths if needed):

```bash
export WHISPER_CPP_DIR="$HOME/whisper.cpp/build/bin"
export WHISPER_CPP_MODEL="$HOME/whisper.cpp/models/ggml-large-v3.bin"
```

The app checks:

- `WHISPER_CPP_BINARY = $WHISPER_CPP_DIR/whisper-cli`
- `WHISPER_CPP_MODEL =` path to `ggml-large-v3.bin`

If both exist, **Local Whisper** will be available and selectable in the UI.

> **Note:** In this project, local Whisper is hard-wired to German by default:
> - The backend forces `lang = "de"` for `whisper.cpp`.
> - This gives best results for German WhatsApp voice messages.

---

## Running the server

In the project directory:

```bash
cd ~/Android_WhatsApp_VoiceTranscription
source .venv/bin/activate   # if you created a venv
python app.py
```

You should see logs similar to:

- Database initialized
- `WHISPER_CPP_BINARY = ... (exists=True/False)`
- `HAS_WHISPER_CPP = True/False`
- And a warning if no providers are available.

By default, Flask runs on `0.0.0.0:5000`.

### Opening the UI

On the **same device** (Android phone):

1. Open your browser (Chrome, Firefox, etc.).
2. Go to:

   - `http://127.0.0.1:5000`  
     or  
   - `http://localhost:5000`

You should see the "WhatsApp Transcriber" interface:

- Button to **find messages**
- Provider dropdown
- "All / None" selection buttons
- A log panel at the bottom

---

## Using the web UI

1. Click **"Nachrichten suchen / Find Messages"**  
   The server scans configured WhatsApp voice notes folders for `.opus` files (most recent first, up to 75 entries).

2. Select messages:
   - Tap a card to select/deselect it.
   - Use **"Alle / All"** and **"Keine / None"** to (de-)select all.

3. Choose provider:
   - **Groq** – remote Whisper API
   - **Local Whisper** – offline `whisper.cpp` (forced German by default)
   - **Gemini** – Google Generative Language API

   If a provider is unavailable (no API key or missing binary/model), it appears disabled and labeled as not available.

4. Click **"Transcribe …"**:
   - The button text updates with progress.
   - For each selected message, you see:
     - A short status line ("Transcribing…")
     - The final transcription (or an error message)
   - Successfully transcribed messages become semi-transparent and unselectable.
   - All transcriptions are stored in `transcripts.db`.

5. Re-loading / caching:
   - When re-scanning messages, already transcribed files are displayed as "transcribed" cards with their saved text.
   - No new API calls are made for those cached entries.

---

## Language of the UI and transcriptions

The web UI and the default transcription language are controlled by a small i18n helper in `index.html`.

### Default behavior

By default, the app automatically chooses the language based on your browser / device language:

- If your browser language starts with `de` (for example `de-DE`):
  - The UI will be shown in **German**.
  - For **Groq** and **Gemini**, the backend will request **German** transcriptions.
  - For **local `whisper.cpp`**, the backend **always** uses German (hard-coded), regardless of UI language.
- Otherwise:
  - The UI will be shown in **English**.
  - For **Groq** and **Gemini**, the backend will request **English** (or at least non-German) transcriptions.

### Changing the UI language without changing system language

If you don’t want to change your entire device language, you have two options.

#### 1. Change browser language (no code changes)

Most browsers let you set a preferred language:

1. Open your browser settings (Chrome / Firefox / Edge, etc.).
2. Search for **“Language”** or **“Languages”**.
3. Move **Deutsch (German)** or **English** to the top of the list.
4. Restart the browser or reload `http://127.0.0.1:5000`.

The UI language and the language used for Groq/Gemini transcriptions should now follow that setting.

#### 2. Force a fixed UI language in `index.html` (code change)

If you always want the UI to use one language, ignoring the browser settings, you can hard-code it.

1. Open `index.html` in an editor.
2. Find the lines near the top of the main script:

   ```js
   let currentLanguage = 'en'; 
   let T = translations[currentLanguage];
   ```

3. Change `'en'` to `'de'` if you want to force German, or keep `'en'` to force English, for example:

   ```js
   let currentLanguage = 'de';
   let T = translations[currentLanguage];
   ```

4. A bit further down, inside `document.addEventListener('DOMContentLoaded', () => { ... })`, you will see:

   ```js
   detectLanguage();
   checkProviderStatus();
   ```

   Replace the `detectLanguage();` call with a direct call to `setLanguage(currentLanguage);` so auto-detection is disabled:

   ```js
   document.addEventListener('DOMContentLoaded', () => {
       setLanguage(currentLanguage);   // use fixed language
       checkProviderStatus();

       const messageList = document.getElementById('message-list');
       const transcribeBtn = document.getElementById('transcribe-btn');
       ...
   });
   ```

Now the UI will always be in the language you set in `currentLanguage`, regardless of browser or system settings.

> **Important notes**
>
> - **Local `whisper.cpp`** is hard-wired to German in `app.py` by default: it always uses `lang="de"` internally unless you change the code (see next section).
> - **Groq** and **Gemini** use the current UI language (`en` or `de`) as the `lang` parameter for the backend and thus influence the transcription language.

### Changing the local `whisper.cpp` transcription language

By default, the local `whisper.cpp` integration always transcribes in **German** (`lang = "de"`), independent of the UI language. You can change this behavior if you want another language.

> **Warning:** Changing the Whisper language may reduce accuracy for German messages. Make sure your `whisper.cpp` model supports the language you choose.

1. Open `app.py` in an editor.
2. Find the function `transcribe_with_whisper_cpp` (near the middle of the file). It looks like this (simplified):

   ```python
   def transcribe_with_whisper_cpp(audio_path, lang="de"):
       if not HAS_WHISPER_CPP:
           return "[FEHLER] whisper.cpp ist nicht installiert oder konfiguriert."

       # FORCE GERMAN: Lokales Whisper ist für deutsche Transkription optimiert
       # Ignoriere Frontend-Spracheinstellung
       lang = "de"
       ...
   ```

3. **Option A – use UI language (recommended if you want multiple languages):**

   Remove or comment out the line that forces `lang = "de"` so the function uses whatever is passed in from the frontend:

   ```python
   def transcribe_with_whisper_cpp(audio_path, lang="de"):
       if not HAS_WHISPER_CPP:
           return "[FEHLER] whisper.cpp ist nicht installiert oder konfiguriert."

       # Remove this line so the passed-in `lang` is used:
       # lang = "de"
       ...
   ```

   After this change, the local Whisper transcription language will follow the `lang` parameter from the frontend, which is based on the current UI language (`en` or `de`) or whatever you pass from the client.

4. **Option B – hard-code a different language:**

   If you always want local Whisper to use a specific language (for example English), keep the override but change the code:

   ```python
   # FORCE ENGLISH instead of German
   lang = "en"
   ```

   You can use any language code supported by `whisper.cpp` (e.g. `en`, `de`, `es`, `fr`, `it`, etc.).

5. Save `app.py` and restart the server:

   ```bash
   python app.py
   ```

Local Whisper will now use the new language setting you configured.

---

## Termux widget (optional)

The repository includes Termux widget scripts to quickly start/stop the transcriber via the Android home screen.

Scripts:

- `termux-widget-scripts/start_transcriber.sh`
- `termux-widget-scripts/stop_transcriber.sh`

### Setup

1. Install **Termux:Widget** from F-Droid.
2. Copy or symlink the scripts into Termux’s widget directory:

   ```bash
   mkdir -p ~/.shortcuts
   cp termux-widget-scripts/start_transcriber.sh ~/.shortcuts/
   cp termux-widget-scripts/stop_transcriber.sh ~/.shortcuts/
   chmod +x ~/.shortcuts/start_transcriber.sh ~/.shortcuts/stop_transcriber.sh
   ```

3. On your Android launcher, add a **Termux:Widget** widget and place the shortcuts on your home screen.

> Make sure your environment variables (API keys, paths) are set up in your shell config (e.g. `~/.bashrc`) if the widget scripts start a new Termux session.

---

## Security & privacy considerations

- **No keys in code:**  
  All provider keys (`GROQ_API_KEY`, `GEMINI_API_KEY`, etc.) are read from environment variables.  
  They are not included in tracked files. Do not paste keys into `app.py`, `README.md`, scripts, or commit them.

- **No phone numbers / user identifiers:**  
  The repository does not contain phone numbers, contact names, or transcripts. Keep it that way:
  - Do not commit `transcripts.db` or any exported transcription files.
  - Do not commit logs that may contain personal message content.

- **Audio data location:**  
  WhatsApp audio files remain on your device:
  - The server only reads from your WhatsApp media folders.
  - The browser UI streams from the local server over `http://127.0.0.1:5000/audio/...`.

- **.gitignore recommendation:**

  Consider adding a `.gitignore` like:

  ```gitignore
  # Python
  __pycache__/
  *.pyc
  .venv/

  # Local data
  transcripts.db
  temp/
  *.log

  # OS / editor
  .DS_Store
  *.swp
  ```

  (Adjust as needed.)

---

## Troubleshooting

- **"WhatsApp folder not found" in UI:**
  - Ensure `termux-setup-storage` was run and permission granted.
  - Check the hard-coded `WHATSAPP_PATHS` in `app.py`. You may need to add or adjust paths depending on your WhatsApp installation:
    - `~/storage/shared/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes`
    - `~/storage/shared/WhatsApp/Media/WhatsApp Voice Notes`
    - `/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes`
    - `/sdcard/WhatsApp/Media/WhatsApp Voice Notes`

- **Provider appears as "not available":**
  - Groq / Gemini: check if `GROQ_API_KEY` and/or `GEMINI_API_KEY` environment variables are set.
  - Local Whisper: check `WHISPER_CPP_DIR` and `WHISPER_CPP_MODEL` and that `whisper-cli` and the model file actually exist.

- **Transcription errors or timeouts:**
  - Check Termux logs (stdout/stderr from `python app.py`).
  - For local Whisper, make sure `ffmpeg` is installed and can convert `.opus` files:
    ```bash
    ffmpeg -i input.opus -ac 1 -ar 16000 -acodec pcm_s16le output.wav
    ```
  - Some providers impose time / size limits; very long voice notes may fail.

---

## License

This project is licensed under the terms described in [`LICENSE`](LICENSE).
