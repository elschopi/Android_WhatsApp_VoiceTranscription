# WhatsApp Voice Transcription (Android / Termux)

A small self‑hosted tool to browse and transcribe your WhatsApp voice notes directly on your Android phone using Termux, a local Flask server, and a simple web UI.

- No WhatsApp modification / root required
- Reads your existing `.opus` voice notes from WhatsApp’s media folder
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
   Opening `http://127.0.0.1:5000` in a browser on your phone shows a Tailwind‑based interface where you:

   - Press **“Nachrichten suchen / Find Messages”** to load recent voice messages  
   - Select messages (or all)  
   - Choose transcription provider: **Groq**, **Local Whisper**, or **Gemini**  
   - Start transcription and see results inline per message (and in a log panel)

3. **Transcription providers:**
   - **Groq Whisper**: remote API (`whisper-large-v3`) with good speed and accuracy.
   - **Local whisper.cpp**: uses `whisper-cli` binary and a local `ggml-large-v3.bin` model.
     - Optimized in this project for **German** voice notes; language is forced to `de`.
   - **Gemini**: Google Generative Language API, used with a prompt to get pure text transcriptions.

4. **Database caching:**
   - A small SQLite database (`transcripts.db`) stores transcriptions keyed by file path.
   - Already transcribed messages are displayed as “transcribed” cards with cached text and no re‑API calls.

---

## Requirements

- **Android phone** with WhatsApp installed
- **Termux** app (from F‑Droid or the official source)
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

1. Install **Termux** from F‑Droid or the official source (not from random Play Store clones).
2. Open Termux and run:

   ```bash
   termux-setup-storage