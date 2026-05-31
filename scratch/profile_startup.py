# scratch/profile_startup.py
import time
import sys

print("[JARVIS PROFILER] Starting Precise JARVIS Startup Profiler...")
results = []

def time_import(module_name):
    t0 = time.perf_counter()
    try:
        __import__(module_name)
        elapsed = (time.perf_counter() - t0) * 1000.0
        results.append((f"Import {module_name}", elapsed))
        print(f"  - {module_name}: {elapsed:.2f} ms")
    except Exception as e:
        print(f"  - {module_name}: Failed ({e})")

# 1. Measure Import Phase
print("\n--- 1. Import Phase timing ---")
time_import("numpy")
time_import("sounddevice")
time_import("webrtcvad")
time_import("psutil")
time_import("tkinter")
time_import("google.genai")
time_import("openwakeword")
time_import("faster_whisper")

# 2. Measure openWakeWord model loading
print("\n--- 2. Wake Word Model Load Phase ---")
t0 = time.perf_counter()
from openwakeword.model import Model
oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
elapsed = (time.perf_counter() - t0) * 1000.0
results.append(("Load openWakeWord (hey_jarvis model)", elapsed))
print(f"  - openWakeWord model load: {elapsed:.2f} ms")

# 3. Measure Faster-Whisper base.en model loading (quantized CPU)
print("\n--- 3. Faster-Whisper Model Load Phase ---")
t0 = time.perf_counter()
from faster_whisper import WhisperModel
model = WhisperModel("base.en", device="cpu", compute_type="int8")
elapsed = (time.perf_counter() - t0) * 1000.0
results.append(("Load Faster-Whisper (base.en int8 CPU)", elapsed))
print(f"  - Faster-Whisper model load: {elapsed:.2f} ms")

# 4. Report Rankings
print("\n--- 4. Summary Rankings (Highest to Lowest Latency) ---")
results.sort(key=lambda x: x[1], reverse=True)
for name, ms in results:
    print(f"  - {name}: {ms:.2f} ms")
