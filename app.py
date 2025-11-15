#!/usr/bin/env python3
import os
import base64
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, Response, send_file
import requests

# Konfiguriere grundlegendes Logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# --- Konfiguration ---
API_KEY = os.getenv("GEMINI_API_KEY", "")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
WHATSAPP_PATHS = [
    Path.home() / "storage/shared/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes",
    Path.home() / "storage/shared/WhatsApp/Media/WhatsApp Voice Notes",
    Path("/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes"),
    Path("/sdcard/WhatsApp/Media/WhatsApp Voice Notes"),
]
DB_FILE = Path(__file__).parent / "transcripts.db"

# Zweisprachige API-Prompts
PROMPTS = {
    "de": "Bitte transkribieren Sie diese Sprachnachricht auf Deutsch. Geben Sie nur die Transkription zurück, ohne zusätzliche Kommentare.",
    "en": "Please transcribe this voice message. Respond only with the transcription, without any additional comments."
}

# --- Datenbank-Hilfsfunktionen ---

def init_db():
    """Initialisiert die Datenbank und erstellt die Tabelle, falls sie nicht existiert."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                transcription_text TEXT NOT NULL,
                transcribed_at DATETIME NOT NULL
            )
        """)
        con.commit()
        con.close()
        app.logger.info(f"[Server] Datenbank initialisiert: {DB_FILE}")
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Initialisieren der DB: {e}")

def get_transcript_from_db(file_path):
    """Holt ein Transkript aus der DB, falls vorhanden."""
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
    """Speichert ein neues Transkript in der DB."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO transcriptions (file_path, file_name, transcription_text, transcribed_at) 
            VALUES (?, ?, ?, ?)
        """, (str(path), str(name), transcription, datetime.now()))
        con.commit()
        con.close()
        app.logger.info(f"[Server] Transkript für {name} in DB gespeichert.")
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Speichern in der DB: {e}")

# --- Hilfsfunktionen ---
def find_whatsapp_folder():
    """Findet den ersten existierenden WhatsApp Voice Notes Ordner."""
    app.logger.info("[Server] Suche nach WhatsApp-Ordner...")
    for path in WHATSAPP_PATHS:
        if path.exists():
            app.logger.info(f"[Server] WhatsApp-Ordner gefunden: {path}")
            return path
    app.logger.warning("[Server] Keinen WhatsApp-Ordner gefunden.")
    return None

def scan_audio_files(base_path):
    """Sucht nach .opus-Dateien im Ordner und sortiert sie nach Datum."""
    if not base_path:
        return []
    try:
        app.logger.info("[Server] Suche nach Audio-Dateien...")
        audio_files = list(base_path.rglob('*.opus'))
        app.logger.info(f"[Server] {len(audio_files)} Nachrichten gefunden.")
        audio_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return audio_files
    except Exception as e:
        app.logger.error(f"[Server] Fehler beim Scannen der Dateien: {e}")
        return []

def transcribe_audio_rest(audio_path, lang="de"):
    """Transkribiert eine einzelne Audiodatei über die Gemini REST API in der gewählten Sprache."""
    if not API_KEY:
        app.logger.error("[Server] GEMINI_API_KEY nicht gesetzt.")
        return "[FEHLER] GEMINI_API_KEY auf dem Server nicht gesetzt."

    app.logger.info(f"[Server] Starte Transkription für: {audio_path.name} (Sprache: {lang})")
    
    prompt_text = PROMPTS.get(lang, PROMPTS["en"])

    try:
        with open(audio_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode('utf-8')

        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": prompt_text
                    },
                    {
                        "inline_data": {
                            "mime_type": "audio/ogg",
                            "data": audio_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048
            }
        }

        url = f"{API_URL}?key={API_KEY}"
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, headers=headers, json=payload, timeout=90)

        if response.status_code != 200:
            app.logger.error(f"[Server] API-Fehler: {response.status_code} - {response.text}")
            return f"[FEHLER] API-Fehler: {response.status_code}. Details siehe Server-Log."

        result = response.json()

        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                text = candidate['content']['parts'][0].get('text', '')
                transcription = text.strip()
                if not transcription:
                    app.logger.warning("[Server] Transkription war leer.")
                    return "[INFO] Transkription war leer."
                app.logger.info(f"[Server] Transkription erfolgreich.")
                return transcription

        app.logger.warning(f"[Server] Unerwartete API-Antwort: {result}")
        return "[FEHLER] Unerwartete API-Antwort."

    except requests.exceptions.Timeout:
        app.logger.error("[Server] API-Anfrage Zeitüberschreitung.")
        return "[FEHLER] Zeitüberschreitung bei der API-Anfrage."
    except Exception as e:
        app.logger.error(f"[Server] Lokaler Fehler bei Transkription: {e}")
        return f"[FEHLER] Lokaler Fehler: {e}"

# --- API Endpunkte ---

@app.route('/')
def index():
    """Liefert die Haupt-HTML-Seite aus."""
    return send_file('index.html')

@app.route('/api/messages')
def get_messages():
    """
    Sucht die Nachrichten, prüft die DB und gibt eine HTML-LISTE zurück.
    """
    folder = find_whatsapp_folder()
    if not folder:
        return '<p class="text-red-400" data-i18n="errorFolderNotFound">WhatsApp-Ordner nicht gefunden.</p>', 500

    audio_files = scan_audio_files(folder)
    if not audio_files:
        return '<p class="text-gray-500" data-i18n="errorNoOpusFiles">Keine .opus-Dateien im Ordner gefunden.</p>'

    html_output = ""
    for audio_file in audio_files[:50]: # Begrenze auf 50
        try:
            file_path_str = str(audio_file)
            stat = audio_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)

            msg_data = {
                "path": file_path_str,
                "name": audio_file.name,
                "date_str": mtime.strftime("%d.%m.%Y"),
                "time_str": mtime.strftime("%H:%M"),
                "size_kb": f"{(stat.st_size / 1024):.1f}"
            }

            safe_path = base64.urlsafe_b64encode(msg_data["path"].encode('utf-8')).decode('utf-8')
            audio_src = f"/audio/{safe_path}"

            existing_transcript = get_transcript_from_db(file_path_str)

            if existing_transcript:
                # Fall 1: Bereits transkribiert
                html_output += f"""
                <div class="message-card-transcribed bg-gray-800/60 p-3 md:p-4 rounded-lg shadow-sm border border-gray-700 opacity-70">
                    <div class="flex items-center gap-3">
                        <svg class="w-5 h-5 text-emerald-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" />
                        </svg>
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-medium text-gray-400 truncate">{msg_data['name']}</div>
                            <div class="text-xs text-gray-500">{msg_data['date_str']} &nbsp; {msg_data['time_str']} <span data-i18n="timeUnit">Uhr</span>  •  {msg_data['size_kb']} KB</div>
                        </div>
                    </div>
                    <audio class="w-full mt-3 h-10" controls src="{audio_src}" preload="none"></audio>
                    <div class="transcription-output mt-3 p-3 bg-gray-700/80 rounded-md text-gray-300 text-sm">
                        {existing_transcript}
                    </div>
                </div>
                """
            else:
                # Fall 2: Neu
                html_output += f"""
                <div class="message-card bg-gray-800 p-3 md:p-4 rounded-lg shadow-md transition-all duration-200 border-2 border-transparent" data-path="{msg_data['path']}">
                    <div class="flex items-center gap-3">
                        <input type="checkbox" data-path="{msg_data['path']}" class="message-checkbox w-5 h-5 rounded text-emerald-500 bg-gray-700 border-gray-600 focus:ring-emerald-600 ring-offset-gray-800 focus:ring-2">
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-medium text-gray-300 truncate">{msg_data['name']}</div>
                            <div class="text-xs text-gray-400">{msg_data['date_str']} &nbsp; {msg_data['time_str']} <span data-i18n="timeUnit">Uhr</span>  •  {msg_data['size_kb']} KB</div>
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

    return Response(html_output, mimetype='text/html')


@app.route('/audio/<path:safe_path>')
def serve_audio(safe_path):
    """Liefert die Audiodatei sicher an den Browser."""
    try:
        file_path_bytes = base64.urlsafe_b64decode(safe_path)
        file_path = file_path_bytes.decode('utf-8')
        folder = find_whatsapp_folder()
        if not (folder and Path(file_path).is_relative_to(folder)):
            app.logger.warning(f"Ungültiger Audio-Pfad angefordert: {file_path}")
            return "Ungültiger Pfad", 403
        return send_file(file_path, mimetype='audio/ogg')
    except Exception as e:
        app.logger.error(f"Fehler beim Senden von Audio: {e}")
        return "Datei nicht gefunden", 404


@app.route('/api/transcribe', methods=['POST'])
def transcribe_message():
    """Nimmt Pfad und Sprache entgegen, transkribiert und SPEICHERT IN DB."""
    data = request.json
    path = data.get('path')
    lang = data.get('lang', 'en') 

    if not path:
        return jsonify({"error": "Kein Pfad angegeben"}), 400

    folder = find_whatsapp_folder()
    if not (folder and Path(path).is_relative_to(folder)):
        return jsonify({"error": "Ungültiger Pfad"}), 403

    try:
        transcription = transcribe_audio_rest(Path(path), lang)
        
        if transcription.startswith("[FEHLER]") or transcription.startswith("[INFO]"):
            return jsonify({"error": transcription}), 500

        save_transcript_to_db(path, Path(path).name, transcription)
        return jsonify({"transcription": transcription})
    except Exception as e:
        app.logger.error(f"Fehler in /api/transcribe: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    init_db()
    if not API_KEY:
        app.logger.warning("===================================================")
        app.logger.warning("WARNUNG: GEMINI_API_KEY ist nicht gesetzt!")
        app.logger.warning("Setze sie mit: export GEMINI_API_KEY='DEIN_KEY_HIER'")
        app.logger.warning("===================================================")
    app.run(host='0.0.0.0', port=5000, debug=False)
