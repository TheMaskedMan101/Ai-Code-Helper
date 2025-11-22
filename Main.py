import os
import sys
import threading
import time
import json
import logging
from typing import Optional
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import pyttsx3
import speech_recognition as sr
import mss
import mss.tools
from rich.console import Console
from openai import OpenAI

try:
    import face_recognition
    FACE_LIB_AVAILABLE = True
except Exception:
    FACE_LIB_AVAILABLE = False

console = Console()

LOG_FILE = "assistant.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def log_info(msg: str):
    logging.info(msg)
    console.log(msg)

def log_error(msg: str):
    logging.error(msg, exc_info=True)
    console.log(f"[red]{msg}[/red]")

log_info("Assistant starting up")

SETTINGS_FILE = "assistant_settings.json"
DEFAULT_SETTINGS = {
    "face_overlay": False,
    "webcam_index": 0,
    "tts_rate": 150,
    "tts_volume": 1.0,
    "auto_write_ai_code_to": "",
}

def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
    except Exception as e:
        log_error(f"Failed to load settings: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(s: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
        log_info("Settings saved")
    except Exception as e:
        log_error(f"Failed to save settings: {e}")

settings = load_settings()

def prompt_api_key() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    key = simpledialog.askstring("API Key Required", "Enter your OpenAI API key:", show="*")
    root.destroy()
    if not key or not key.strip():
        messagebox.showerror("Error", "API key is required. Exiting.")
        sys.exit(1)
    return key.strip()

api_key_env = os.getenv("OPENAI_API_KEY")
if api_key_env:
    api_key = api_key_env.strip()
    log_info("Using OPENAI_API_KEY from environment")
else:
    api_key = prompt_api_key()
    log_info("API key obtained from user input")

openai_client = OpenAI(api_key=api_key)
DEFAULT_MODEL = "gpt-4o"

def ask_ai(prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1500) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    try:
        response = openai_client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.2
        )
        text = response.choices[0].message.content.strip()
        log_info("AI call success")
        return text
    except Exception as e:
        log_error(f"AI request failed: {e}")
        return f"[AI request failed: {e}]"

tts_engine = None
try:
    tts_engine = pyttsx3.init()
    tts_engine.setProperty("rate", settings.get("tts_rate", 150))
    tts_engine.setProperty("volume", settings.get("tts_volume", 1.0))
    log_info("TTS engine initialized")
except Exception as e:
    tts_engine = None
    log_error(f"TTS init failed: {e}")

def tts_speak(text: str):
    if tts_engine:
        try:
            tts_engine.say(text)
            tts_engine.runAndWait()
        except Exception as e:
            log_error(f"TTS error: {e}")
    else:
        log_info(f"TTS unavailable, skipping speech: {text[:50]}...")

recognizer = sr.Recognizer()
mic = None
try:
    mic = sr.Microphone()
    log_info("Microphone initialized")
except Exception as e:
    mic = None
    log_error(f"Microphone init failed (PyAudio may be missing): {e}")

listening_flag = threading.Event()

def background_listen_loop(callback):
    if not mic:
        log_error("Microphone not available")
        return
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        log_info("Microphone calibrated")
    except Exception as e:
        log_error(f"Microphone calibration failed: {e}")
        return
    
    while listening_flag.is_set():
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            try:
                text = recognizer.recognize_google(audio)
                callback(text)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                text = f"[STT error: {e}]"
                callback(text)
        except Exception as e:
            log_error(f"Background listen error: {e}")
            time.sleep(1)

def safe_read_file(path: str) -> str:
    try:
        if not os.path.exists(path):
            return f"[File not found: {path}]"
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[Error reading file: {e}]"

def safe_write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        log_info(f"Wrote {len(content)} bytes to {path}")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"[Error writing file: {e}]"

DANGEROUS_TOKENS = ["rm -rf", ":(){:|:&};:", "shutdown", "reboot", "format", "mkfs", "dd if="]
import subprocess

def is_risky_command(cmd: str) -> bool:
    lower = cmd.lower()
    for t in DANGEROUS_TOKENS:
        if t in lower:
            return True
    if "sudo" in lower:
        return True
    for prefix in ("del ", "rm ", "rmdir ", "format "):
        if lower.strip().startswith(prefix):
            return True
    return False

def run_command(cmd: str, allow_interactive: bool = False) -> str:
    try:
        if allow_interactive:
            p = subprocess.run(cmd, shell=True)
            return f"Return code: {p.returncode}"
        else:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = p.stdout or ""
            err = p.stderr or ""
            if err:
                return f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
            return out if out else f"Command completed with return code {p.returncode}"
    except subprocess.TimeoutExpired:
        return "[Error: Command timed out after 30 seconds]"
    except Exception as e:
        return f"[Error running command: {e}]"

def capture_screen(output_path: str) -> str:
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            if len(monitors) > 1:
                monitor = monitors[1]
            else:
                monitor = monitors[0]
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=output_path)
        log_info(f"Captured screen to {output_path}")
        return f"Saved screenshot to {output_path}"
    except Exception as e:
        log_error(f"Screen capture error: {e}")
        return f"[Error capturing screen: {e}]"

class AssistantApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("AI Desktop Assistant")
        self.running = True
        
        webcam_idx = settings.get("webcam_index", 0)
        self.cap = None
        try:
            self.cap = cv2.VideoCapture(webcam_idx)
            if not self.cap.isOpened():
                log_error(f"Webcam {webcam_idx} failed to open")
                self.cap = None
        except Exception as e:
            log_error(f"Webcam init error: {e}")
            self.cap = None
        
        self.webcam_w, self.webcam_h = 320, 240
        
        top = tk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X)
        self.cam_label = tk.Label(top, text="Webcam unavailable", width=40, height=15, bg="gray")
        self.cam_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        right = tk.Frame(top)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        btns = tk.Frame(right)
        btns.pack(side=tk.TOP, pady=4)
        
        self.listen_btn = tk.Button(btns, text="Start Listening", command=self.toggle_listen)
        self.listen_btn.grid(row=0, column=0, padx=3, pady=3)
        tk.Button(btns, text="Ask AI", command=self.ask_ai_dialog).grid(row=0, column=1, padx=3)
        tk.Button(btns, text="Capture Screen", command=self.capture_screen_gui).grid(row=0, column=2, padx=3)
        tk.Button(btns, text="Open File", command=self.open_file_gui).grid(row=1, column=0, padx=3)
        tk.Button(btns, text="Run Command", command=self.run_command_gui).grid(row=1, column=1, padx=3)
        tk.Button(btns, text="Settings", command=self.open_settings).grid(row=1, column=2, padx=3)
        tk.Button(btns, text="Quit", command=self.quit).grid(row=2, column=2, padx=3, pady=3)
        
        self.text = tk.Text(right, height=12, wrap=tk.WORD)
        self.text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.face_overlay = settings.get("face_overlay", False)
        self.listening = False
        self.listen_thread = None
        
        self.update_webcam()
        self.log_print("Assistant ready")

    def log_print(self, msg: str):
        def _update():
            self.text.insert(tk.END, msg + "\n")
            self.text.see(tk.END)
        if threading.current_thread() == threading.main_thread():
            _update()
        else:
            self.root.after(0, _update)
        log_info(msg)

    def update_webcam(self):
        try:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.resize(frame, (self.webcam_w, self.webcam_h))
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    if self.face_overlay and FACE_LIB_AVAILABLE:
                        try:
                            small = cv2.resize(rgb, (0, 0), fx=0.5, fy=0.5)
                            boxes = face_recognition.face_locations(small)
                            for (top, right, bottom, left) in boxes:
                                top *= 2
                                right *= 2
                                bottom *= 2
                                left *= 2
                                cv2.rectangle(rgb, (left, top), (right, bottom), (0, 255, 0), 2)
                        except Exception as e:
                            log_error(f"Face overlay error: {e}")
                    
                    img = Image.fromarray(rgb)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.cam_label.config(image=imgtk, text="")
                    self.cam_label.image = imgtk
        except Exception as e:
            log_error(f"Webcam update error: {e}")
        
        if self.running:
            self.root.after(30, self.update_webcam)

    def toggle_listen(self):
        if not self.listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        if not mic:
            messagebox.showerror("No mic", "No microphone available. Install PyAudio for Windows.")
            return
        self.listening = True
        listening_flag.set()
        self.listen_btn.config(text="Stop Listening")
        self.log_print("Listening started")
        self.listen_thread = threading.Thread(
            target=background_listen_loop,
            args=(self.on_speech_recognized,),
            daemon=True
        )
        self.listen_thread.start()

    def stop_listening(self):
        self.listening = False
        listening_flag.clear()
        self.listen_btn.config(text="Start Listening")
        self.log_print("Listening stopped")

    def on_speech_recognized(self, text: str):
        def _handle():
            self.log_print(f"[Mic] {text}")
            lowered = text.lower().strip()
            if lowered.startswith("ask ai") or lowered.startswith("ask"):
                parts = text.split(maxsplit=2)
                prompt = parts[-1] if len(parts) >= 2 else text
                self.run_ai(prompt)
            elif lowered.startswith("run "):
                cmd = text[4:]
                if is_risky_command(cmd):
                    if not messagebox.askyesno("Risky command", f"Voice command appears risky:\n{cmd}\nRun anyway?"):
                        self.log_print("[Voice] Command aborted by user")
                        return
                self.log_print(f"[Voice] Running command: {cmd}")
                threading.Thread(
                    target=lambda: self.log_print(run_command(cmd)),
                    daemon=True
                ).start()
            else:
                threading.Thread(
                    target=tts_speak,
                    args=(f"You said: {text}",),
                    daemon=True
                ).start()
        self.root.after(0, _handle)

    def ask_ai_dialog(self):
        prompt = simpledialog.askstring("Ask AI", "Enter prompt for AI:")
        if prompt:
            self.run_ai(prompt)

    def run_ai(self, prompt: str):
        self.log_print(f"[AI] Prompt: {prompt}")
        
        def _call():
            resp = ask_ai(prompt, max_tokens=1500)
            self.log_print("[AI Response]")
            self.log_print(resp)
            
            try:
                threading.Thread(
                    target=tts_speak,
                    args=(resp[:300],),
                    daemon=True
                ).start()
            except Exception:
                pass
            
            def _ask_save():
                if messagebox.askyesno("Save AI response?", "Save AI response to file?"):
                    p = filedialog.asksaveasfilename(defaultextension=".txt")
                    if p:
                        self.log_print(safe_write_file(p, resp))
                
                aw = settings.get("auto_write_ai_code_to")
                if aw:
                    self.log_print(safe_write_file(aw, resp))
            
            self.root.after(0, _ask_save)
        
        threading.Thread(target=_call, daemon=True).start()

    def capture_screen_gui(self):
        p = filedialog.asksaveasfilename(defaultextension=".png", initialfile="screenshot.png")
        if not p:
            return
        r = capture_screen(p)
        self.log_print(r)
        threading.Thread(
            target=tts_speak,
            args=(f"Screenshot saved",),
            daemon=True
        ).start()

    def open_file_gui(self):
        p = filedialog.askopenfilename()
        if not p:
            return
        content = safe_read_file(p)
        win = tk.Toplevel(self.root)
        win.title(f"File: {os.path.basename(p)}")
        txt = tk.Text(win, wrap=tk.WORD)
        txt.insert("1.0", content)
        txt.pack(fill=tk.BOTH, expand=True)
        
        def ask_edit():
            instr = simpledialog.askstring("Edit instruction", "Describe edits to request from AI:")
            if not instr:
                return
            prompt = f"Original file content:\n```\n{content}\n```\n\nEdit request: {instr}\nReturn full updated file."
            
            def _do_edit():
                updated = ask_ai(prompt, max_tokens=2000)
                
                def _confirm():
                    if not updated:
                        messagebox.showerror("AI Error", "No response from AI")
                        return
                    if messagebox.askyesno("Overwrite?", "AI returned updated content. Overwrite file?"):
                        result = safe_write_file(p, updated)
                        self.log_print(result)
                        txt.delete("1.0", tk.END)
                        txt.insert("1.0", updated)
                
                self.root.after(0, _confirm)
            
            threading.Thread(target=_do_edit, daemon=True).start()
        
        tk.Button(win, text="Ask AI to Edit & Overwrite", command=ask_edit).pack(side=tk.BOTTOM, pady=4)

    def run_command_gui(self):
        cmd = simpledialog.askstring("Run command", "Enter shell command:")
        if not cmd:
            return
        if is_risky_command(cmd):
            if not messagebox.askyesno("Risky command", f"The command appears risky:\n{cmd}\nRun anyway?"):
                self.log_print("[Command] Aborted by user")
                return
        allow_interactive = messagebox.askyesno("Interactive", "Allow interactive mode?")
        self.log_print(f"[Run] {cmd}")
        threading.Thread(
            target=lambda: self.log_print(run_command(cmd, allow_interactive)),
            daemon=True
        ).start()

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        
        face_var = tk.BooleanVar(value=self.face_overlay)
        tk.Checkbutton(win, text="Enable face overlay", variable=face_var).pack(anchor="w", padx=5, pady=3)
        tk.Label(win, text=f"face_recognition available: {FACE_LIB_AVAILABLE}").pack(anchor="w", padx=5)
        
        tk.Label(win, text="Webcam index:").pack(anchor="w", padx=5)
        idx_var = tk.IntVar(value=settings.get("webcam_index", 0))
        tk.Entry(win, textvariable=idx_var).pack(anchor="w", padx=5)
        
        tk.Label(win, text="Auto-write AI output file:").pack(anchor="w", padx=5)
        aw_var = tk.StringVar(value=settings.get("auto_write_ai_code_to", ""))
        tk.Entry(win, textvariable=aw_var, width=40).pack(anchor="w", padx=5)
        
        tk.Label(win, text="TTS rate:").pack(anchor="w", padx=5)
        rate_var = tk.IntVar(value=settings.get("tts_rate", 150))
        tk.Entry(win, textvariable=rate_var).pack(anchor="w", padx=5)
        
        def save():
            settings["face_overlay"] = face_var.get()
            self.face_overlay = face_var.get()
            settings["webcam_index"] = idx_var.get()
            settings["auto_write_ai_code_to"] = aw_var.get().strip()
            settings["tts_rate"] = rate_var.get()
            
            if tts_engine:
                try:
                    tts_engine.setProperty("rate", settings["tts_rate"])
                except Exception as e:
                    log_error(f"Failed to update TTS rate: {e}")
            
            save_settings(settings)
            messagebox.showinfo("Settings", "Saved. Some changes (webcam index) require restart.")
            win.destroy()
        
        tk.Button(win, text="Save Settings", command=save).pack(pady=6)

    def quit(self):
        if messagebox.askyesno("Quit", "Quit the assistant?"):
            self.running = False
            if self.cap:
                self.cap.release()
            listening_flag.clear()
            self.root.quit()
            log_info("Assistant quitting")

def main():
    root = tk.Tk()
    try:
        app = AssistantApp(root)
        root.protocol("WM_DELETE_WINDOW", app.quit)
        root.mainloop()
    except Exception as e:
        log_error(f"Fatal GUI error: {e}")
        messagebox.showerror("Fatal Error", f"Application crashed: {e}")

if __name__ == "__main__":
    main()
