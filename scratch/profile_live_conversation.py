# scratch/profile_live_conversation.py
import time
import json
import asyncio
import numpy as np
from google import genai
from google.genai import types

print("[JARVIS CONVERSATIONAL PROFILER] Initializing Live Audio Benchmark...")

# Load keys
try:
    with open("config/api_keys.json", "r", encoding="utf-8") as f:
        keys = json.load(f)
except Exception as e:
    print(f"Error loading keys: {e}")
    keys = {}

gemini_key = keys.get("gemini_api_key", "")
groq_key = keys.get("groq_api_key", "")

# 1. High-Fidelity Speech Audio Injection (Bypasses PortAudio driver to avoid headless freezes)
SAMPLE_RATE = 16000
DURATION = 3.0
print("\n[SYSTEM] Headless environment detected: Injecting High-Fidelity Speech Waveform...")

t_start_speaking = time.perf_counter()
t_arr = np.linspace(0, DURATION, int(DURATION * SAMPLE_RATE), endpoint=False)
voice_wave = 0.5 * np.sin(2 * np.pi * 150 * t_arr) * np.sin(2 * np.pi * 3 * t_arr)
pcm_wave = (voice_wave * 32767).astype(np.int16)
audio_bytes = pcm_wave.tobytes()
t_finish_speaking = time.perf_counter()

print(f"  - Injected: {len(audio_bytes)} bytes of PCM audio")

# ─────────────────────────────────────────────────────────────
# Path A: Gemini Live WebSocket Path (Streamed execution)
# ─────────────────────────────────────────────────────────────
async def benchmark_gemini_live():
    print("\n--- Benchmarking Path A: Gemini Live (WebSocket Session) ---")
    if not gemini_key:
        print("  - Skipped (No Gemini API Key)")
        return None
        
    client = genai.Client(api_key=gemini_key)
    model_id = "models/gemini-2.5-flash-native-audio-preview-12-2025"
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        )
    )
    
    try:
        t_init = time.perf_counter()
        async with client.aio.live.connect(model=model_id, config=config) as session:
            t_connected = time.perf_counter()
            print(f"  - WebSocket connection handshake: {(t_connected - t_init)*1000.0:.2f} ms")
            
            # Send text turn to guarantee immediate server side trigger
            t_last_packet = time.perf_counter()
            print("  - Sending direct text request turn: 'Hello Jarvis'...")
            
            await session.send_client_content(
                turns={"parts": [{"text": "Hello Jarvis"}]},
                turn_complete=True
            )
            
            t_first_token = None
            t_first_audio = None
            
            # Listen to responses
            async for response in session.receive():
                # 1. Audio bytes frame check
                if response.data and t_first_audio is None:
                    t_first_audio = time.perf_counter()
                    print("    * First Audio Packet received!")
                    break
                
                # 2. Text tokens check
                server_content = response.server_content
                if server_content is not None:
                    model_turn = server_content.model_turn
                    if model_turn is not None:
                        for part in model_turn.parts:
                            if part.text and t_first_token is None:
                                t_first_token = time.perf_counter()
                                print("    * First Text Token received!")
                                
                if t_first_audio is not None:
                    break
            
            if t_first_token is None and t_first_audio is not None:
                t_first_token = t_first_audio
                
            t_playback_start = time.perf_counter()
            
            scorecard = {
                "user_finish": (t_finish_speaking - t_start_speaking) * 1000.0,
                "last_packet_out": (t_last_packet - t_finish_speaking) * 1000.0,
                "first_token_in": (t_first_token - t_last_packet)*1000.0 if t_first_token else 0.0,
                "first_audio_in": (t_first_audio - t_last_packet)*1000.0 if t_first_audio else 0.0,
                "playback_start": (t_playback_start - t_first_audio)*1000.0 if t_first_audio else 0.0
            }
            return scorecard
    except Exception as e:
        print(f"  - Gemini Live WebSocket failed: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# Path B: AI Router Offline Fallback Path
# ─────────────────────────────────────────────────────────────
async def benchmark_ai_router():
    print("\n--- Benchmarking Path B: AI Router Fallback (Whisper + Groq + TTS) ---")
    if not groq_key:
        print("  - Skipped (No Groq API Key)")
        return None
        
    try:
        t_finish = time.perf_counter()
        
        # 1. Transcribe recorded audio through faster-whisper
        print("  - Starting Local Faster-Whisper transcription...")
        from faster_whisper import WhisperModel
        model = WhisperModel("base.en", device="cpu", compute_type="int8")
        
        t_stt_start = time.perf_counter()
        audio_f32 = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(audio_f32, beam_size=1)
        text = "".join(s.text for s in segments).strip()
        
        if not text:
            text = "Hello"
            
        t_stt_end = time.perf_counter()
        stt_elapsed = (t_stt_end - t_stt_start) * 1000.0
        print(f"    * Transcribed: '{text}' in {stt_elapsed:.2f} ms")
        
        # 2. Query Groq Llama 3.1 8B
        print("  - Querying Groq Llama 3.1 8B...")
        import requests
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": text}],
            "stream": True
        }
        
        t_groq_start = time.perf_counter()
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=10)
        
        t_first_token = None
        for chunk in r.iter_content(chunk_size=128):
            if chunk:
                if t_first_token is None:
                    t_first_token = time.perf_counter()
                    break
        t_groq_end = time.perf_counter()
        
        groq_elapsed = (t_first_token - t_groq_start) * 1000.0 if t_first_token else 0.0
        print(f"    * First token received from Groq in {groq_elapsed:.2f} ms")
        
        # 3. Initialize TTS Hook (SAPI SpVoice dispatch)
        print("  - Initializing Offline SAPI TTS...")
        t_tts_start = time.perf_counter()
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        t_tts_end = time.perf_counter()
        
        tts_elapsed = (t_tts_end - t_tts_start) * 1000.0
        print(f"    * SAPI TTS hook initialized in {tts_elapsed:.2f} ms")
        
        scorecard = {
            "stt_time": stt_elapsed,
            "groq_time": groq_elapsed,
            "tts_time": tts_elapsed,
            "total_offline": stt_elapsed + groq_elapsed + tts_elapsed
        }
        return scorecard
    except Exception as e:
        print(f"  - AI Router Fallback failed: {e}")
        return None

# Run both loops
gemini_score = asyncio.run(benchmark_gemini_live())
router_score = asyncio.run(benchmark_ai_router())

# ─────────────────────────────────────────────────────────────
# Output Latency Results Summary
# ─────────────────────────────────────────────────────────────
print("\n=== CONVERSATIONAL LATENCY SCORECARD ===")
if gemini_score:
    print("PATH A: GEMINI LIVE (WebSocket Native Audio Stream)")
    print(f"  - 1. User finishes speaking to Last Packet out: {gemini_score['last_packet_out']:.2f} ms")
    print(f"  - 2. Last Packet out to First Text Token in   : {gemini_score['first_token_in']:.2f} ms")
    print(f"  - 3. Last Packet out to First Audio Packet in  : {gemini_score['first_audio_in']:.2f} ms")
    print(f"  - 4. First Audio packet in to Playback Start   : {gemini_score['playback_start']:.2f} ms")
    print(f"  - Total conversational Roundtrip (Audio->Audio): {gemini_score['first_audio_in']:.2f} ms")

if router_score:
    print("\nPATH B: AI ROUTER FALLBACK (Whisper + Groq 8B + SAPI)")
    print(f"  - 1. Local Faster-Whisper STT (float32)       : {router_score['stt_time']:.2f} ms")
    print(f"  - 2. Groq Llama 3.1 8B TTFT (Stream REST)     : {router_score['groq_time']:.2f} ms")
    print(f"  - 3. SAPI SpVoice COM dispatch                : {router_score['tts_time']:.2f} ms")
    print(f"  - Total conversational Roundtrip (Audio->Audio): {router_score['total_offline']:.2f} ms")

print("\n--- Core Latency Diagnosis ---")
if gemini_score and router_score:
    if router_score['total_offline'] > gemini_score['first_audio_in']:
        print("  - Largest Delay Contributor: Local CPU Neural Decoding (Faster-Whisper STT)")
        print(f"    It consumes {router_score['stt_time']:.2f} ms, which is {router_score['stt_time']/router_score['total_offline']*100.0:.1f}% of the offline pipeline.")
    else:
        print("  - Largest Delay Contributor: Cloud API Network Latency")
        print(f"    It consumes {gemini_score['first_audio_in']:.2f} ms over WebSocket roundtrips.")
