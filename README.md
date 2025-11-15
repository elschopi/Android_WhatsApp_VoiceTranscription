[readme_eng.md](https://github.com/user-attachments/files/23562974/readme_eng.md)
WhatsApp Voice Note Transcriber for TermuxThis project turns your Android phone into a private transcription server. It uses Termux to run a small Python web server that finds your WhatsApp voice notes, lists them in a clean web interface (accessed via your phone's browser), and transcribes them using the Google Gemini API.Transcribed messages are saved to a local SQLite database (transcripts.db), so the next time you load the app, they appear instantly with their transcription and aren't processed again.FeaturesBilingual Web Interface: Automatically detects browser language (German/English) and sets the UI text.Gemini API: Uses Google's Gemini API, which natively understands .opus files (no conversion needed).Local Database: Remembers previously transcribed messages.Termux Widget Support: Includes scripts to start/stop the server from your homescreen.Wakelock Handling: Scripts automatically acquire a Termux wakelock to prevent Android from killing the server in the background.Privacy-Focused: Audio files are only sent to the API when you explicitly transcribe them. The web server runs entirely locally.Prerequisites: Required AppsInstall these apps (ideally from F-Droid, as the Google Play Store versions of Termux are deprecated):Termux: The main terminal environment.Termux:API (App): Provides the bridge between Termux and native Android functions.Termux:Widget: Allows you to place script launchers (widgets) on your homescreen.Installation GuideStep 1: Clone This RepositoryIn Termux, clone this repository to a location you choose, for example ~/whatsapp-transcriber.pkg install git
git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git) ~/whatsapp-transcriber
cd ~/whatsapp-transcriber
Step 2: Set Up Termux EnvironmentInstall Packages: Install Python, Termux:API, and nano (or your preferred editor).pkg update && pkg upgrade -y
pkg install python termux-api nano -y
Install Python Libraries:pip install flask requests
Grant Storage Access:termux-setup-storage
(You must approve the Android permission dialog that pops up.)Step 3: Set Your Google Gemini API KeyGo to Google AI Studio and create an API key.Save the key in your Termux environment. The start script will automatically load this.(Replace YOUR_API_KEY_HERE with your actual key.)echo 'export GEMINI_API_KEY="YOUR_API_KEY_HERE"' >> ~/.bashrc
source ~/.bashrc
Step 4: Install the Widget ScriptsCreate the shortcuts folder:mkdir -p ~/.shortcuts
Copy the scripts from this repository into the shortcuts folder:cp ~/whatsapp-transcriber/termux-widget-scripts/*.sh ~/.shortcuts/
Make the scripts executable (CRITICAL):chmod +x ~/.shortcuts/start_transcriber.sh
chmod +x ~/.shortcuts/stop_transcriber.sh
Step 5: Add the WidgetGo to your Android Homescreen.Long-press an empty space and select "Widgets".Find and add the "Termux:Widget".The widget should now show start_transcriber.sh and stop_transcriber.sh.How to UseStart: Tap the start_transcriber.sh widget on your homescreen. Your browser should automatically open and load http://localhost:5000.Find: Tap "Find Messages". The server will scan your WhatsApp folders.Transcribe: Select one or more messages and tap the blue "Transcribe" button.Stop: When you're finished, tap the stop_transcriber.sh widget. This stops the server and releases the wakelock to save battery.Project Structure/
├── .gitignore              # Ignores logs, database, and cache
├── LICENSE                 # MIT License
├── README.md               # This guide (English)
├── README_DE.md            # German guide
├── app.py                  # The Python Flask server (Backend)
├── index.html              # The Bilingual Web App (Frontend)
└── termux-widget-scripts/
    ├── start_transcriber.sh    # Homescreen start script
    └── stop_transcriber.sh     # Homescreen stop script
