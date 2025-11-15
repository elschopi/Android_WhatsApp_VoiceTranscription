#!/data/data/com.termux/files/usr/bin/bash

# Setze einen Standard-PATH, damit Befehle wie 'python' und 'termux-toast' gefunden werden
export PATH="/data/data/com.termux/files/usr/bin:$PATH"

# Signalisiere Android, dass dieser Prozess wichtig ist und nicht beendet werden soll.
termux-wake-lock

# LADE DIE UMGEBUNGSVARIABLEN (HIER IST DEIN API KEY DRIN!)
if [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc"
    echo "Termux: .bashrc geladen." >&2
elif [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc"
    echo "Termux: .zshrc geladen." >&2
fi

# Setze das Verzeichnis deiner App
# WICHTIG: Pfad anpassen, falls dein Repo-Ordner anders heißt
APP_DIR="$HOME/whatsapp-transcriber"
PID_FILE="$APP_DIR/server.pid"
LOG_FILE="$APP_DIR/server.log"

# Stelle sicher, dass das App-Verzeichnis existiert
mkdir -p "$APP_DIR"
cd "$APP_DIR" || exit

# Prüfe, ob der Server bereits läuft
if [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
    termux-toast "Server läuft bereits!"
    # Öffne trotzdem den Browser, falls er geschlossen wurde
    termux-open-url "http://localhost:5000"
    # Beende das Skript, aber NICHT den Wakelock (der wird vom laufenden Prozess gehalten)
    exit 0
fi

# Prüfe, ob der API Key jetzt geladen ist
if [ -z "$GEMINI_API_KEY" ]; then
    termux-toast "FEHLER: GEMINI_API_KEY nicht gefunden!"
    echo "FEHLER: GEMINI_API_KEY nicht gefunden! Bitte in ~/.bashrc eintragen." >> "$LOG_FILE"
    # Gib den Wakelock bei einem Fehler wieder frei
    termux-wake-unlock
    exit 1
fi

# Starte den Server im Hintergrund
nohup python app.py >> "$LOG_FILE" 2>&1 &

# Speichere die Prozess-ID (PID)
echo $! > "$PID_FILE"

termux-toast "Transcriber-Server gestartet..."

# Warte 2 Sekunden, damit der Server hochfahren kann
sleep 2

# Öffne die URL im Standardbrowser
termux-open-url "http://localhost:5000"
