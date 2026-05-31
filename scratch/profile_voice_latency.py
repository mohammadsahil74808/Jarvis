# scratch/profile_voice_latency.py
import time
import numpy as np

print("[JARVIS VOICE LATENCY PROFILER] Initializing Benchmark...")
results = {}

# 1. Benchmark Wake Word Inference Latency (openWakeWord ONNX)
print("\n--- 1. Wake Word Inference Step ---")
try:
    from openwakeword.model import Model
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    # Generate 1280 samples of 16kHz audio (80ms of silence)
    dummy_frame = np.zeros(1280, dtype=np.int16)
    
    # Warm up ONNX runtime
    oww.predict(dummy_frame)
    
    # Benchmark 10 iterations to get average latency
    t_sum = 0
    for _ in range(10):
        t0 = time.perf_counter()
        oww.predict(dummy_frame)
        t_sum += (time.perf_counter() - t0) * 1000.0
    
    avg_ww_ms = t_sum / 10.0
    results["Stage 1: Wake Word ONNX inference"] = avg_ww_ms
    print(f"  - openWakeWord ONNX inference (1280 samples): {avg_ww_ms:.2f} ms")
except Exception as e:
    avg_ww_ms = 0.0
    print(f"  - openWakeWord Benchmark Failed ({e})")

# 2. Benchmark Voice Activity Detection (VAD) frame processing
print("\n--- 2. VAD Frame Processing Step ---")
try:
    import webrtcvad
    vad = webrtcvad.Vad(3) # Aggressiveness level 3
    # 30ms frame at 16kHz is 480 samples = 960 bytes
    dummy_vad_frame = b'\x00' * 960
    
    # Benchmark
    t_sum = 0
    for _ in range(50):
        t0 = time.perf_counter()
        vad.is_speech(dummy_vad_frame, 16000)
        t_sum += (time.perf_counter() - t0) * 1000.0
        
    avg_vad_ms = t_sum / 50.0
    results["Stage 2: WebRTC VAD check"] = avg_vad_ms
    print(f"  - WebRTC VAD frame check (30ms frame): {avg_vad_ms:.2f} ms")
except Exception as e:
    avg_vad_ms = 0.0
    print(f"  - WebRTC VAD Benchmark Failed ({e})")

# 3. Benchmark Local Offline Transcription (Faster-Whisper)
print("\n--- 3. Local Offline STT (Faster-Whisper base.en int8) ---")
try:
    from faster_whisper import WhisperModel
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    
    # Generate 3 seconds of silence (which loads fast without triggering looping search steps)
    dummy_audio = np.zeros(16000 * 3, dtype=np.float32)
    
    # Warm up model
    model.transcribe(dummy_audio, beam_size=1)
    
    # Benchmark
    t0 = time.perf_counter()
    segments, _ = model.transcribe(dummy_audio, beam_size=1)
    list(segments) # Force iterator consumption
    whisper_ms = (time.perf_counter() - t0) * 1000.0
    results["Stage 3: Offline Whisper STT"] = whisper_ms
    print(f"  - Transcribe 3s audio segment: {whisper_ms:.2f} ms")
except Exception as e:
    whisper_ms = 0.0
    print(f"  - Faster-Whisper Benchmark Failed ({e})")

# 4. Benchmark LLM API Roundtrip (Online Cloud connection)
print("\n--- 4. Cloud API Latency (Multi-Tier Chain) ---")
try:
    import urllib.request
    import json
    
    # We query a fast public text endpoint to measure real network roundtrip
    url = "https://text.pollinations.ai/"
    data = json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode("utf-8")
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    )
    
    # Benchmark real network transit + response generation
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as response:
        response.read()
    network_ms = (time.perf_counter() - t0) * 1000.0
    results["Stage 4: Cloud LLM API Roundtrip"] = network_ms
    print(f"  - Cloud LLM request roundtrip: {network_ms:.2f} ms")
except Exception as e:
    network_ms = 0.0
    print(f"  - Cloud LLM Benchmark Failed ({e})")

# 5. Benchmark TTS Hook time
print("\n--- 5. Offline SAPI TTS Hook time ---")
try:
    import win32com.client
    t0 = time.perf_counter()
    # Instantiate COM object
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    elapsed_tts = (time.perf_counter() - t0) * 1000.0
    results["Stage 5: Offline SAPI TTS Hook"] = elapsed_tts
    print(f"  - SAPI SpVoice COM dispatch: {elapsed_tts:.2f} ms")
except Exception as e:
    elapsed_tts = 0.0
    print(f"  - SAPI TTS Benchmark Failed ({e})")

# 6. Report Full Scorecard
print("\n=== LATENCY SCORECARD SUMMARY ===")
for name, ms in results.items():
    print(f"  - {name}: {ms:.2f} ms")

print("\n--- Diagnostic Findings ---")
# Find the largest delay contributor
slowest_stage = max(results, key=results.get)
print(f"  * Single Largest Delay Contributor: {slowest_stage}")
print(f"    Consumed: {results[slowest_stage]:.2f} ms")
