import os
import sys
import time
import subprocess
import numpy as np
import sounddevice as sd
import psutil
import threading
import socket
from pynput import keyboard
from pathlib import Path

# --- Configuration ---
THRESHOLD = 20000        # Amplitude threshold (max ~32767 for int16)
RATIO = 7.0              # Peak-to-average ratio (spike sensitivity)
COOLDOWN = 2.0           # Seconds between launch attempts
SAMPLE_RATE = 16000      # Audio sampling rate
CHUNK_SIZE = 1024        # Buffer size
ASSISTANT_FILE = "main.py"

BASE_DIR = Path(__file__).resolve().parent

class ClapLauncher:
    def __init__(self):
        self.last_launch_time = 0
        self.is_running = True
        self.assistant_is_running_cached = False
        self.clap_detected = threading.Event()
        
        # --- Shift Trigger Config ---
        self.last_shift_time = 0
        self.last_trigger_time = 0
        self.shift_cooldown = 2.0  # Seconds between successful activations
        self.shift_pressed = False
        
        # Start Shift Listener
        self.kb_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.kb_listener.start()

        # Start a background thread to check process status
        self.monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
        self.monitor_thread.start()

    def _monitor_process(self):
        """Background thread that periodically checks if JARVIS is running."""
        while self.is_running:
            self.assistant_is_running_cached = self.is_assistant_running()
            time.sleep(3) # Check every 3 seconds, not in the audio loop!

    def is_assistant_running(self):
        """Checks if main.py is already running."""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if cmdline and any(ASSISTANT_FILE in arg for arg in cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def _on_press(self, key):
        """Keyboard press handler for Shift detection."""
        if key == keyboard.Key.shift:
            if not self.shift_pressed:
                self.shift_pressed = True
                now = time.time()
                
                # Check for 2.0s trigger cooldown
                if now - self.last_trigger_time < self.shift_cooldown:
                    return

                # Check for double tap window (400ms)
                if now - self.last_shift_time < 0.4:
                    print(f"[Launcher] ⌨️ Double Shift detected!")
                    self.last_trigger_time = now
                    self.last_shift_time = 0 # Avoid triple shift
                    self.activate_assistant()
                else:
                    self.last_shift_time = now

    def _on_release(self, key):
        """Keyboard release handler."""
        if key == keyboard.Key.shift:
            self.shift_pressed = False

    def activate_assistant(self):
        """Main entry point for any trigger (Clap or Key)."""
        # Refresh process check immediately
        is_running = self.is_assistant_running()
        
        if not is_running:
            self.launch_assistant()
        else:
            print("[Launcher] 🔔 JARVIS is already running. Signaling Wake...")
            self.send_wake_signal()

    def send_wake_signal(self):
        """Sends UDP packet to main.py to wake it up."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(b"WAKE", ("127.0.0.1", 9999))
            sock.close()
        except Exception as e:
            print(f"[Launcher] ❌ Signal Error: {e}")

    def launch_assistant(self):
        """Launches main.py in a separate process."""
        print(f"[Launcher] 🚀 Launching {ASSISTANT_FILE}...")
        try:
            # Use sys.executable to ensure we use the same Python interpreter
            # subprocess.Popen allows the launcher to keep running independently
            subprocess.Popen([sys.executable, str(BASE_DIR / ASSISTANT_FILE)], 
                             creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
        except Exception as e:
            print(f"[Launcher] ❌ Error launching assistant: {e}")

    def audio_callback(self, indata, frames, time_info, status):
        """Analyze audio chunk for claps."""
        if status:
            print(f"[Launcher] ⚠️ Audio Error: {status}")
            
        abs_data = np.abs(indata)
        peak = np.max(abs_data)
        
        if peak > THRESHOLD:
            avg = np.mean(abs_data)
            if avg > 0 and (peak / avg) > RATIO:
                now = time.time()
                if now - self.last_launch_time > COOLDOWN:
                    print(f"[Launcher] 👏 Clap detected! Peak: {int(peak)}")
                    self.last_launch_time = now
                    
                    if not self.assistant_is_running_cached:
                        self.launch_assistant()
                    else:
                        print("[Launcher] ℹ️ JARVIS is already running. Signaling Wake via Clap...")
                        self.send_wake_signal()

    def run(self):
        print(f"[Launcher] 👂 System Monitoring Active. Waiting for clap...")
        print(f"[Launcher] ⚙️ Threshold: {THRESHOLD}, Ratio: {RATIO}")
        
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE,
                                channels=1,
                                dtype='int16',
                                blocksize=CHUNK_SIZE,
                                callback=self.audio_callback):
                while self.is_running:
                    time.sleep(1)
        except Exception as e:
            print(f"[Launcher] ❌ Microphone Error: {e}")
            print("Please ensure your microphone is connected and accessible.")

if __name__ == "__main__":
    launcher = ClapLauncher()
    launcher.run()
