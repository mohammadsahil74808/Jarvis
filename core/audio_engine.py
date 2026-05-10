# core/audio_engine.py  ← REPLACE your existing file with this
# ══════════════════════════════════════════════════════════════
# JARVIS Audio Engine — UPGRADED v2
# Changes from original:
#   1. WebRTC VAD integration (optional — auto-detects if installed)
#   2. Whisper fallback transcription (when Gemini is offline)
#   3. Queue-based audio chunk splitting for VAD (10ms chunks)
#   4. Graceful degradation — if webrtcvad not installed, uses original behavior
# ══════════════════════════════════════════════════════════════

import asyncio
import threading
import traceback
from core.config import (
    CHANNELS, CHUNK_SIZE, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE
)


def _lazy_sd():
    import sounddevice as sd
    return sd


class AudioEngine:
    def __init__(self, jarvis):
        self.jarvis    = jarvis
        self._loop     = None

        # ── VAD Engine (optional upgrade) ─────────────────────
        # If webrtcvad is installed, we use it for better speech detection.
        # If not, falls back to the original behavior (no change for user).
        self._vad = None
        self._vad_enabled = False
        self._try_init_vad()

    # ─────────────────────────────────────────────────────────
    def _try_init_vad(self):
        """Try to initialize WebRTC VAD. Silent fail if not installed."""
        try:
            import webrtcvad
            from core.vad_engine import VADEngine
            self._vad = VADEngine(
                on_speech_end=self._on_vad_speech_end,
                sample_rate=SEND_SAMPLE_RATE,
                aggressiveness=3,
                sensitivity=0.4,
            )
            self._vad_enabled = True
            print("[AudioEngine] ✓ WebRTC VAD active")
        except ImportError:
            self._vad_enabled = False
            print("[AudioEngine] WebRTC VAD not installed — using standard mode")
            print("             (Install: pip install webrtcvad)")
        except Exception as e:
            self._vad_enabled = False
            print(f"[AudioEngine] VAD init failed: {e} — using standard mode")

    def _on_vad_speech_end(self, audio_numpy):
        """
        Callback from VAD when a speech segment ends.
        Used ONLY when Gemini is offline — routes to Whisper fallback.
        """
        if self.jarvis.session:
            return  # Gemini is online — don't intercept

        # Gemini offline → transcribe locally
        if hasattr(self.jarvis, "whisper_fb") and self.jarvis.whisper_fb.is_ready:
            text = self.jarvis.whisper_fb.transcribe(audio_numpy)
            if text and text.strip():
                print(f"[AudioEngine] Whisper: '{text}'")
                self.jarvis._on_text_command(text)

    # ─────────────────────────────────────────────────────────
    async def send_realtime_loop(self):
        """Sends audio chunks to the Gemini Live session."""
        while True:
            msg = await self.jarvis.out_queue.get()
            # Block audio during tool calls OR when model is speaking
            with self.jarvis._speaking_lock:
                busy = (
                    getattr(self.jarvis, "tool_call_pending", False)
                    or self.jarvis._is_speaking
                )

            if busy:
                continue
            if self.jarvis.session:
                try:
                    await self.jarvis.session.send_realtime_input(media=msg)
                except Exception as e:
                    print(f"[AudioEngine] Send error: {e}")

    # ─────────────────────────────────────────────────────────
    async def detection_loop(self):
        """Offloaded clap and wake word detection."""
        while True:
            try:
                indata = await self.jarvis.detection_queue.get()

                with self.jarvis._speaking_lock:
                    jarvis_speaking = self.jarvis._is_speaking

                if jarvis_speaking:
                    continue

                # ── Clap Detection ────────────────────────────
                if self.jarvis.clap_enabled and self.jarvis.detector:
                    if self.jarvis.detector.is_clap(indata):
                        print("[JARVIS] Clap detected!")
                        if self.jarvis.ui.muted:
                            self.jarvis.ui.root.after(0, self.jarvis.ui._toggle_mute)
                        else:
                            self.jarvis.ui.write_log("SYS: Clap detected (Already active).")

                # ── Wake Word Detection ───────────────────────
                if self.jarvis.wake_word_enabled and self.jarvis.wake_detector:
                    if self.jarvis.wake_detector.check(indata):
                        print("[JARVIS] Wake word detected!")
                        if self.jarvis.ui.muted:
                            self.jarvis.ui.root.after(0, self.jarvis.ui._toggle_mute)
                        else:
                            self.jarvis.ui.write_log("SYS: Wake word detected (Already active).")

                # ── VAD: Feed audio to WebRTC VAD ─────────────
                # This handles Whisper offline fallback only.
                # Does NOT affect normal Gemini Live operation.
                if self._vad_enabled and self._vad and not self.jarvis.session:
                    raw = indata.tobytes()
                    self._vad.process_large_chunk(raw)

            except Exception as e:
                print(f"[AudioEngine] Detection error: {e}")
            finally:
                self.jarvis.detection_queue.task_done()

    # ─────────────────────────────────────────────────────────
    async def listen_loop(self):
        """Captures microphone audio and routes to queues."""
        print("[AudioEngine] Mic started")
        self._loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            # ── Route to detection queue (clap + wake word) ──
            if self.jarvis.clap_enabled or self.jarvis.wake_word_enabled:
                self._loop.call_soon_threadsafe(
                    self.jarvis.detection_queue.put_nowait, indata.copy()
                )

            # ── Route to Gemini Live send queue ───────────────
            with self.jarvis._speaking_lock:
                jarvis_speaking = self.jarvis._is_speaking

            if not jarvis_speaking and not self.jarvis.ui.muted:
                data = indata.tobytes()
                self._loop.call_soon_threadsafe(
                    self.jarvis.out_queue.put_nowait,
                    {"data": data, "mime_type": "audio/pcm"}
                )

        while True:
            try:
                with _lazy_sd().InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    callback=callback,
                ):
                    print("[AudioEngine] Mic stream open")
                    while True:
                        await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[AudioEngine] Mic Error: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    # ─────────────────────────────────────────────────────────
    async def play_loop(self):
        """Plays received audio chunks from Gemini."""
        print("[AudioEngine] Play started")
        stream = _lazy_sd().RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                chunk = await self.jarvis.audio_in_queue.get()
                self.jarvis.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
                if self.jarvis.audio_in_queue.empty():
                    await asyncio.sleep(0.15)
                    if self.jarvis.audio_in_queue.empty():
                        self.jarvis.set_speaking(False)
        except Exception as e:
            print(f"[AudioEngine] Play error: {e}")
            raise
        finally:
            self.jarvis.set_speaking(False)
            stream.stop()
            stream.close()
