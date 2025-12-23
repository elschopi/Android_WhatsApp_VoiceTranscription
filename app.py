#!/usr/bin/env python3
import os
import base64
import logging
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, Response, send_file
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# --- Konfiguration ---
API_KEY = os.getenv("GEMINI_API_KEY", "")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"

WHISPER_CPP_DIR = Path(os.getenv("WHISPER_CPP_DIR", Path.home() / "whisper.cpp" / "build" / "bin"))
WHISPER_CPP_MODEL = Path(os.getenv("WHISPER_CPP_MODEL", Path.home() / "whisper.cpp" / "models" / "ggml-large-v3.bin"))
WHISPER_CPP_BINARY = WHISPER_CPP_DIR / "whisper-cli"
HAS_WHISPER_CPP = WHISPER_CPP_BINARY.exists() and WHISPER_CPP_MODEL.exists()

WHATSAPP_PATHS = [
    Path.home() / "storage/shared/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes",
    Path.home() / "storage/shared/WhatsApp/Media/WhatsApp Voice Notes",
    Path("/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes"),
    Path("/sdcard/WhatsApp/Media/WhatsApp Voice Notes"),
]
DB_FILE = Path(__file__).parent / "transcripts.db"

PROMPTS = {
    "de": "Deine Ausgabesprache ist Deutsch. Bitte transkribiere diese Nachricht. Gib nur den Text zurück, ohne zusätzliche Kommentare.",
    "en": "Please transcribe this voice message. Respond only with the transcription, without any additional comments.",
}

# --- DB ---

def init_db():
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                transcription_text TEXT NOT NULL,
                transcribed_at DATETIME NOT NULL
            )
            """
        )
        con.commit()
        con.close()
        app.logger.info(f"[Server] Datenbank initialisiert: {DB_FILE}")
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Initialisieren der DB: {e}")


def get_transcript_from_db(file_path):
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute("SELECT transcription_text FROM transcriptions WHERE file_path = ?", (str(file_path),))
        result = cur.fetchone()
        con.close()
        return result[0] if result else None
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Lesen aus der DB: {e}")
        return None


def save_transcript_to_db(path, name, transcription):
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO transcriptions (file_path, file_name, transcription_text, transcribed_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(path), str(name), transcription, datetime.now()),
        )
        con.commit()
        con.close()
        app.logger.info(f"[Server] Transkript für {name} in DB gespeichert.")
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Speichern in der DB: {e}")


# --- Helper ---

def find_whatsapp_folder():
    app.logger.info("[Server] Suche nach WhatsApp-Ordner...")
    for path in WHATSAPP_PATHS:
        if path.exists():
            app.logger.info(f"[Server] WhatsApp-Ordner gefunden: {path}")
            return path
    app.logger.warning("[Server] Keinen WhatsApp-Ordner gefunden.")
    return None


def scan_audio_files(base_path):
    if not base_path:
        return []
    try:
        app.logger.info("[Server] Suche nach Audio-Dateien...")
        audio_files = list(base_path.rglob("*.opus"))
        app.logger.info(f"[Server] {len(audio_files)} Nachrichten gefunden.")
        audio_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return audio_files
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Scannen der Dateien: {e}")
        return []


# --- Gemini ---

def transcribe_with_gemini(audio_path, lang="de"):
    if not API_KEY:
        app.logger.error("[Server] GEMINI_API_KEY nicht gesetzt.")
        return "[FEHLER] GEMINI_API_KEY auf dem Server nicht gesetzt."

    app.logger.info(f"[Server] [Gemini] Starte Transkription für: {audio_path.name} (Sprache: {lang})")
    prompt_text = PROMPTS.get(lang, PROMPTS["de"])

    try:
        with open(audio_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": "audio/ogg", "data": audio_data}},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }

        url = f"{API_URL}?key={API_KEY}"
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, json=payload, timeout=90)

        if response.status_code != 200:
            app.logger.error(f"[Server] [Gemini] API-Fehler: {response.status_code} - {response.text}")
            return f"[FEHLER] API-Fehler (Gemini): {response.status_code}. Details siehe Server-Log."

        result = response.json()
        if "candidates" in result and result["candidates"]:
            candidate = result["candidates"][0]
            parts = candidate.get("content", {}).get("parts", [])
            if parts:
                text = parts[0].get("text", "")
                transcription = text.strip()
                return transcription or "[INFO] Transkription war leer."
        return "[FEHLER] Unerwartete API-Antwort (Gemini)."
    except requests.exceptions.Timeout:
        return "[FEHLER] Zeitüberschreitung bei der API-Anfrage (Gemini)."
    except Exception as e:
        return f"[FEHLER] Lokaler Fehler (Gemini): {e}"


# --- Groq Whisper ---

def transcribe_with_groq(audio_path, lang="de"):
    if not GROQ_API_KEY:
        return "[FEHLER] GROQ_API_KEY auf dem Server nicht gesetzt."

    app.logger.info(f"[Server] [Groq] Starte Transkription für: {audio_path.name} (Sprache: {lang})")
    prompt_text = PROMPTS.get(lang, PROMPTS["de"])

    try:
        with open(audio_path, "rb") as audio_file:
            files = {"file": (audio_path.name, audio_file)}
            data = {
                "model": GROQ_MODEL,
                "language": lang,
                "response_format": "text",
                "temperature": 0,
                "prompt": prompt_text,
            }
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            response = requests.post(GROQ_STT_URL, headers=headers, files=files, data=data, timeout=90)

        if response.status_code != 200:
            app.logger.error(f"[Server] [Groq] API-Fehler: {response.status_code} - {response.text}")
            return f"[FEHLER] API-Fehler (Groq): {response.status_code}. Details siehe Server-Log."

        transcription = response.text.strip()
        return transcription or "[INFO] Transkription war leer."
    except requests.exceptions.Timeout:
        return "[FEHLER] Zeitüberschreitung bei der API-Anfrage (Groq)."
    except Exception as e:
        return f"[FEHLER] Lokaler Fehler (Groq): {e}"


# --- whisper.cpp (lokal) ---

def transcribe_with_whisper_cpp(audio_path, lang="de"):
    """
    Transkribiert eine Audiodatei mit whisper.cpp über whisper-cli.
    WICHTIG: Ignoriert den lang-Parameter und erzwingt IMMER Deutsch,
    da lokales Whisper für deutsche WhatsApp-Nachrichten optimiert ist.
    """
    if not HAS_WHISPER_CPP:
        return "[FEHLER] whisper.cpp ist nicht installiert oder konfiguriert."

    # FORCE GERMAN: Lokales Whisper ist für deutsche Transkription optimiert
    # Ignoriere Frontend-Spracheinstellung
    lang = "de"

    app.logger.info(f"[Server] [whisper.cpp] Starte Transkription für: {audio_path.name} (ERZWINGE Sprache: {lang})")

    temp_dir = Path(__file__).parent / "temp"
    temp_dir.mkdir(exist_ok=True)

    temp_wav = temp_dir / f"temp_{audio_path.stem}_{os.getpid()}.wav"
    output_base = temp_dir / f"transcript_{audio_path.stem}_{os.getpid()}"
    output_txt = Path(f"{output_base}.txt")

    try:
        # Schritt 1: .opus -> WAV mit ffmpeg
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", str(audio_path),
            "-ac", "1",
            "-ar", "16000",
            "-acodec", "pcm_s16le",
            "-y",
            str(temp_wav),
        ]
        app.logger.info(f"[Server] [whisper.cpp] ffmpeg CMD: {' '.join(ffmpeg_cmd)}")
        ffmpeg_result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)

        if ffmpeg_result.returncode != 0:
            app.logger.error(f"[Server] [whisper.cpp] ffmpeg Fehler: {ffmpeg_result.stderr[:500]}")
            return f"[FEHLER] ffmpeg Konvertierung fehlgeschlagen: {ffmpeg_result.stderr[:200]}"

        if not temp_wav.exists() or temp_wav.stat().st_size == 0:
            return "[FEHLER] WAV-Konvertierung fehlgeschlagen (Datei leer oder nicht erstellt)"

        app.logger.info(f"[Server] [whisper.cpp] WAV erstellt: {temp_wav.name} ({temp_wav.stat().st_size} bytes)")

        # Schritt 2: whisper-cli mit dokumentierter Syntax aufrufen
        # -m MODEL -l de -otxt -of OUTPUT_BASE -f INPUT_WAV
        # KEIN -tr Flag = transkribieren (nicht übersetzen)
        whisper_cmd = [
            str(WHISPER_CPP_BINARY),
            "-m", str(WHISPER_CPP_MODEL),
            "-l", lang,  # Immer "de"
            "-otxt",
            "-of", str(output_base),
            "-f", str(temp_wav),
        ]

        app.logger.info(f"[Server] [whisper.cpp] whisper-cli CMD: {' '.join(whisper_cmd)}")

        whisper_result = subprocess.run(whisper_cmd, capture_output=True, text=True, timeout=300)

        app.logger.info(f"[Server] [whisper.cpp] returncode={whisper_result.returncode}")
        if whisper_result.stderr:
            app.logger.info(f"[Server] [whisper.cpp] stderr: {whisper_result.stderr[:500]}")
        if whisper_result.stdout:
            app.logger.info(f"[Server] [whisper.cpp] stdout: {whisper_result.stdout[:500]}")

        if whisper_result.returncode != 0:
            msg = whisper_result.stderr.strip() or whisper_result.stdout.strip() or "unknown error"
            return f"[FEHLER] whisper.cpp Fehler: {msg[:300]}"

        if not output_txt.exists():
            app.logger.error(f"[Server] [whisper.cpp] Ausgabedatei nicht gefunden: {output_txt}")
            app.logger.error(f"[Server] [whisper.cpp] Dateien in {temp_dir}: {list(temp_dir.glob('*'))}")
            return "[FEHLER] whisper.cpp hat keine Ausgabedatei erstellt."

        with open(output_txt, "r", encoding="utf-8") as f:
            transcription = f.read().strip()

        app.logger.info(f"[Server] [whisper.cpp] Transkription erfolgreich: {len(transcription)} Zeichen")
        return transcription or "[INFO] Transkription war leer."

    except subprocess.TimeoutExpired:
        app.logger.error("[Server] [whisper.cpp] Timeout nach 5 Minuten.")
        return "[FEHLER] whisper.cpp Timeout (>5 Min)."
    except Exception as e:
        app.logger.error(f"[Server] [whisper.cpp] Lokaler Fehler: {e}")
        return f"[FEHLER] Lokaler Fehler (whisper.cpp): {e}"
    finally:
        # Aufräumen: temp WAV und txt löschen
        try:
            if temp_wav.exists():
                temp_wav.unlink()
                app.logger.info(f"[Server] [whisper.cpp] Temp WAV gelöscht: {temp_wav.name}")
        except Exception as e:
            app.logger.warning(f"[Server] [whisper.cpp] Konnte temp WAV nicht löschen: {e}")

        try:
            if output_txt.exists():
                output_txt.unlink()
                app.logger.info(f"[Server] [whisper.cpp] Temp TXT gelöscht: {output_txt.name}")
        except Exception as e:
            app.logger.warning(f"[Server] [whisper.cpp] Konnte temp TXT nicht löschen: {e}")


# --- Provider-Wrapper & Status ---

def transcribe_audio_rest(audio_path, lang="de", provider="groq"):
    """Provider-Auswahl (Gemini, Groq, lokal)."""
    provider = (provider or "groq").lower()

    if provider == "gemini":
        return transcribe_with_gemini(audio_path, lang)
    elif provider == "local":
        # Lokaler Whisper: IMMER Deutsch, ignoriere Frontend-Sprache
        return transcribe_with_whisper_cpp(audio_path, lang="de")
    else:
        return transcribe_with_groq(audio_path, lang)


@app.route("/api/status")
def api_status():
    """Verfügbarkeit der Provider für das Frontend."""
    status = {
        "groq_available": bool(GROQ_API_KEY),
        "gemini_available": bool(API_KEY),
        "local_whisper_available": bool(HAS_WHISPER_CPP),
    }
    app.logger.info(f"[Server] /api/status -> {status}")
    return jsonify(status)


# --- Endpunkte ---

@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/messages")
def get_messages():
    folder = find_whatsapp_folder()
    if not folder:
        return '<p class="text-red-400" data-i18n="errorFolderNotFound">WhatsApp-Ordner nicht gefunden.</p>', 500

    audio_files = scan_audio_files(folder)
    if not audio_files:
        return '<p class="text-gray-500" data-i18n="errorNoOpusFiles">Keine .opus-Dateien im Ordner gefunden.</p>'

    html_output = ""
    for audio_file in audio_files[:75]:
        try:
            file_path_str = str(audio_file)
            stat = audio_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            msg_data = {
                "path": file_path_str,
                "name": audio_file.name,
                "date_str": mtime.strftime("%d.%m.%Y"),
                "time_str": mtime.strftime("%H:%M"),
                "size_kb": f"{(stat.st_size / 1024):.1f}",
            }
            safe_path = base64.urlsafe_b64encode(msg_data["path"].encode("utf-8")).decode("utf-8")
            audio_src = f"/audio/{safe_path}"
            existing_transcript = get_transcript_from_db(file_path_str)

            if existing_transcript:
                html_output += f"""
                <div class="message-card-transcribed bg-gray-800/60 p-3 md:p-4 rounded-lg shadow-sm border border-gray-700 opacity-70">
                    <div class="flex items-center gap-3">
                        <svg class="w-5 h-5 text-emerald-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" />
                        </svg>
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-medium text-gray-400 truncate">{msg_data['name']}</div>
                            <div class="text-xs text-gray-500">{msg_data['date_str']} &nbsp; {msg_data['time_str']} <span data-i18n="timeUnit">Uhr</span> • {msg_data['size_kb']} KB</div>
                        </div>
                    </div>
                    <audio class="w-full mt-3 h-10" controls src="{audio_src}" preload="none"></audio>
                    <div class="transcription-output mt-3 p-3 bg-gray-700/80 rounded-md text-gray-300 text-sm">
                        {existing_transcript}
                    </div>
                </div>
                """
            else:
                html_output += f"""
                <div class="message-card bg-gray-800 p-3 md:p-4 rounded-lg shadow-md transition-all duration-200 border-2 border-transparent" data-path="{msg_data['path']}">
                    <div class="flex items-center gap-3">
                        <input type="checkbox" data-path="{msg_data['path']}" class="message-checkbox w-5 h-5 rounded text-emerald-500 bg-gray-700 border-gray-600 focus:ring-emerald-600 ring-offset-gray-800 focus:ring-2">
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-medium text-gray-300 truncate">{msg_data['name']}</div>
                            <div class="text-xs text-gray-400">{msg_data['date_str']} &nbsp; {msg_data['time_str']} <span data-i18n="timeUnit">Uhr</span> • {msg_data['size_kb']} KB</div>
                        </div>
                    </div>
                    <audio class="w-full mt-3 h-10" controls src="{audio_src}" preload="none"></audio>
                    <div data-path="{msg_data['path']}" class="transcription-output mt-3 p-3 bg-gray-700 rounded-md text-gray-300 text-sm italic hidden" data-i18n="waitingForTranscription">
                        Warte auf Transkription...
                    </div>
                </div>
                """
        except Exception as e:
            app.logger.error(f"Fehler beim Erstellen der HTML-Karte: {e}")

    if not html_output:
        return '<p class="text-gray-500" data-i18n="errorNoMessagesFound">Keine Nachrichten gefunden oder Fehler beim Verarbeiten.</p>'

    return Response(html_output, mimetype="text/html")


@app.route("/audio/<path:safe_path>")
def serve_audio(safe_path):
    try:
        file_path_bytes = base64.urlsafe_b64decode(safe_path)
        file_path = file_path_bytes.decode("utf-8")
        folder = find_whatsapp_folder()
        if not (folder and Path(file_path).is_relative_to(folder)):
            return "Ungültiger Pfad", 403
        return send_file(file_path, mimetype="audio/ogg")
    except Exception:
        return "Datei nicht gefunden", 404


@app.route("/api/transcribe", methods=["POST"])
def transcribe_message():
    data = request.json
    path = data.get("path")
    lang = data.get("lang", "en")
    provider = data.get("provider", "groq")

    if not path:
        return jsonify({"error": "Kein Pfad angegeben"}), 400

    folder = find_whatsapp_folder()
    if not (folder and Path(path).is_relative_to(folder)):
        return jsonify({"error": "Ungültiger Pfad"}), 403

    try:
        transcription = transcribe_audio_rest(Path(path), lang, provider)
        if transcription.startswith("[FEHLER]") or transcription.startswith("[INFO]"):
            return jsonify({"error": transcription}), 500
        save_transcript_to_db(path, Path(path).name, transcription)
        return jsonify({"transcription": transcription})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Main ---
if __name__ == "__main__":
    init_db()
    app.logger.info(f"[Server] WHISPER_CPP_BINARY = {WHISPER_CPP_BINARY} (exists={WHISPER_CPP_BINARY.exists()})")
    app.logger.info(f"[Server] WHISPER_CPP_MODEL  = {WHISPER_CPP_MODEL} (exists={WHISPER_CPP_MODEL.exists()})")
    app.logger.info(f"[Server] HAS_WHISPER_CPP   = {HAS_WHISPER_CPP}")

    if HAS_WHISPER_CPP:
        app.logger.info("[Server] ⚠️  Lokales Whisper ist auf DEUTSCH festgelegt (ignoriert Frontend-Sprache)")

    if not API_KEY and not GROQ_API_KEY and not HAS_WHISPER_CPP:
        app.logger.warning("====")
        app.logger.warning("WARNUNG: Weder GEMINI_API_KEY, GROQ_API_KEY noch whisper.cpp sind verfügbar!")
        app.logger.warning("====")

    app.run(host="0.0.0.0", port=5000, debug=False)
