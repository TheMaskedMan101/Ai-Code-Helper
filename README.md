# Ai-Code-Helper
Helps you with code i dont know if it fully is working yet feel free to edit the code
make sure to compile the files before running have fun
here is some more info:


# AI Desktop Assistant for Windows

A full-featured AI desktop assistant with GUI, webcam preview, speech recognition, text-to-speech, and AI integration.

## ⚠️ Important Notice

**This is a Windows-specific desktop application.** It requires:
- Windows OS (for full hardware support)
- Physical webcam (optional)
- Microphone with PyAudio (optional, for speech recognition)
- Display for GUI

While the code can be developed in this Replit environment, it's designed to run on a Windows desktop computer.

## Features

✅ **Tkinter GUI** - Clean desktop interface with live webcam preview  
✅ **Webcam Preview** - Real-time camera feed with optional face recognition overlay  
✅ **Speech Recognition** - Voice commands via microphone (requires PyAudio)  
✅ **Text-to-Speech** - Offline voice responses using pyttsx3  
✅ **Screen Capture** - Screenshot functionality with file save  
✅ **AI Integration** - OpenAI GPT-4 for intelligent responses  
✅ **File Operations** - Read, write, and AI-assisted editing  
✅ **Safe Command Execution** - Run system commands with safety checks  
✅ **Logging** - Action and error logging to file  
✅ **Persistent Settings** - JSON-based configuration storage  

## Installation (Windows)

1. **Install Python 3.11+**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

2. **Install Required Packages**
   ```bash
   pip install openai Pillow opencv-python pyttsx3 speechrecognition mss rich
   ```

3. **Install PyAudio (Required for Speech Recognition on Windows)**
   ```bash
   pip install PyAudio
   ```
   
   If you encounter issues, download the appropriate wheel file from:
   https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

4. **Optional: Install Face Recognition**
   ```bash
   pip install face_recognition
   ```
   Note: This requires dlib and cmake, which can be complex on Windows.

## Configuration

### API Key Setup

The application will prompt for your OpenAI API key on startup via a dialog box. The key is:
- **NOT saved to disk** (security feature)
- Stored in memory only for the session
- Can also be set via environment variable: `OPENAI_API_KEY`

### Settings

Access settings through the GUI (Settings button). Configurable options:

- **Face Overlay**: Enable/disable face recognition rectangles (requires `face_recognition` package)
- **Webcam Index**: Camera device ID (usually 0 for default camera)
- **Auto-write AI Code**: Automatically save AI responses to a specified file
- **TTS Rate**: Speech speed (words per minute)

Settings are saved to `assistant_settings.json`.

## Usage

### Running the Application

```bash
python main.py
```

On first run, you'll be prompted to enter your OpenAI API key.

### Voice Commands

Click "Start Listening" and try:
- "Ask AI [your question]" - Send question to AI
- "Run [command]" - Execute a system command
- Any other speech will be echoed back via TTS

### GUI Features

- **Ask AI**: Type a question for the AI assistant
- **Capture Screen**: Save a screenshot to file
- **Open File**: View file contents and optionally ask AI to edit
- **Run Command**: Execute shell commands (with safety warnings)
- **Settings**: Configure webcam, face overlay, TTS, etc.

### Safety Features

The application includes safety checks for:
- Risky commands (`rm`, `del`, `format`, `shutdown`, etc.)
- File overwrites (confirmation dialogs)
- Command timeouts (30 seconds)
- Exception handling (won't crash on errors)

### AI-Assisted File Editing

1. Click "Open File" and select a file
2. Click "Ask AI to Edit & Overwrite"
3. Describe your desired changes
4. Review AI's response and confirm overwrite

## File Structure

```
.
├── main.py                      # Single-file application
├── assistant_settings.json      # Persistent settings (auto-created)
├── assistant.log                # Activity and error log
└── README.md                    # This file
```

## Troubleshooting

### "Microphone init failed"
- Install PyAudio: `pip install PyAudio`
- On Windows, you may need to download a precompiled wheel

### "Webcam unavailable"
- Check webcam is connected and not in use by another app
- Try changing "Webcam Index" in Settings (0, 1, 2, etc.)

### "TTS init failed"
- pyttsx3 should work offline on Windows
- Ensure Windows speech engines are installed

### "face_recognition" errors
- This package is optional and complex to install on Windows
- The app works fine without it (just no face overlay feature)

### API Errors
- Verify your OpenAI API key is valid
- Check your internet connection
- Ensure you have API credits available

## Security Notes

- **API Key**: Never saved to disk, only in memory
- **Command Execution**: Risky commands require explicit confirmation
- **File Operations**: Overwrite confirmations enabled by default
- **Logging**: Actions logged to `assistant.log` for audit trail

## Development Notes

This application demonstrates:
- ✅ Modern OpenAI API (client-based)
- ✅ Threading for responsive GUI
- ✅ Thread-safe GUI updates using `root.after()`
- ✅ Graceful hardware initialization failures
- ✅ Comprehensive error handling
- ✅ Single-file architecture for easy distribution

## License

This is a demonstration project. Modify and use as needed.

## Credits

Built with:
- OpenAI GPT-4 API
- Tkinter (Python standard library)
- OpenCV (webcam)
- pyttsx3 (TTS)
- SpeechRecognition (STT)
- mss (screen capture)
- face_recognition (optional)

