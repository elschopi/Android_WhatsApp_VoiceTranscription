#!/data/data/com.termux/files/usr/bin/bash

# Setze einen Standard-PATH, damit 'termux-toast' und 'kill' gefunden werden
export PATH="/data/data/com.termux/files/usr/bin:$PATH"

# WICHTIG: Pfad anpassen, falls dein Repo-Ordner anders heißt
APP_DIR="$HOME/whatsapp-transcriber"
PID_FILE="$APP_DIR/server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        # Beende den Prozess
        kill "$PID"
        termux-toast "Transcriber-Server gestoppt."
    else
        termux-toast "Server-Prozess nicht gefunden, räume auf."
    fi
    # Entferne die PID-Datei
    rm "$PID_FILE"
else
    termux-toast "Server läuft anscheinend nicht."
fi

# Gib den Wakelock IMMER frei, wenn dieses Skript ausgeführt wird.
termux-wake-unlock
