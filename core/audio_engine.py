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
from core.config import (
    CHANNELS, CHUNK_SIZE, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE
)
from core.utils import lazy_sd



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
        """Initialize VAD Engine (WebRTC if available, or built-in NumPy energy detector)."""
        try:
            from core.vad_engine import VADEngine
            self._vad = VADEngine(
                on_speech_end=self._on_vad_speech_end,
                sample_rate=SEND_SAMPLE_RATE,
                aggressiveness=3,
                sensitivity=0.4,
            )
            self._vad_enabled = True
            print("[AudioEngine] ✓ Voice Activity Detection (VAD) active")
        except Exception as e:
            self._vad_enabled = False
            print(f"[AudioEngine] VAD init failed: {e} — using standard mode")

    def stop(self):
        """Stop audio engine loops if any."""
        pass


    def _on_vad_speech_end(self, audio_numpy):
        """
        Callback from VAD when a speech segment ends.
        Used ONLY when Gemini is offline — routes to Whisper fallback.
        """
        if self.jarvis.session:
            return  # Gemini is online — don't intercept

        # Gemini offline → transcribe locally
        model = getattr(self.jarvis, "whisper_fb", None)
        if model is not None:
            try:
                import numpy as np
                # Convert int16 [-32768, 32767] → float32 [-1.0, 1.0] for faster-whisper
                audio_f32 = audio_numpy.astype(np.float32) / 32768.0
                segments, _ = model.transcribe(audio_f32, beam_size=1, vad_filter=True)
                text = "".join(s.text for s in segments).strip()
                if text:
                    print(f"[AudioEngine] Faster-Whisper: '{text}'")
                    self.jarvis._on_text_command(text)
            except Exception as e:
                print(f"[AudioEngine] Faster-Whisper error: {e}")

    # ─────────────────────────────────────────────────────────
    async def send_realtime_loop(self):
        """Sends audio chunks to the Gemini Live session."""
        while True:
            msg = await self.jarvis.out_queue.get()

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

                # Allowed to detect clap/wake-word even when speaking (Barge-in)

                # ── Clap Detection ────────────────────────────
                if self.jarvis.clap_enabled and self.jarvis.detector:
                    if self.jarvis.detector.is_clap(indata):
                        print("[JARVIS] Clap detected!")
                        if self.jarvis.ui.muted:
                            self.jarvis.ui.root.after(0, self.jarvis.ui._toggle_mute)
                        else:
                            self.jarvis.interrupt_speaking()
                            self.jarvis.ui.write_log("SYS: Barge-in triggered by clap.")

                # ── Wake Word Detection ───────────────────────
                if self.jarvis.wake_word_enabled and self.jarvis.wake_detector:
                    if self.jarvis.wake_detector.check(indata):
                        print("[JARVIS] Wake word detected!")
                        if self.jarvis.ui.muted:
                            self.jarvis.ui.root.after(0, self.jarvis.ui._toggle_mute)
                        else:
                            self.jarvis.interrupt_speaking()
                            self.jarvis.ui.write_log("SYS: Barge-in triggered by wake word.")

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
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(
                        self.jarvis.detection_queue.put_nowait, indata.copy()
                    )

            # ── Route to Gemini Live send queue (Full-Duplex) ─
            if not self.jarvis.ui.muted:
                data = indata.tobytes()
                
                # Extract RMS energy and pass to UI
                if hasattr(self.jarvis.ui, "set_mic_energy"):
                    try:
                        import numpy as np
                        rms = np.sqrt(np.mean(np.square(indata.astype(np.float32)))) / 32768.0
                        self.jarvis.ui.set_mic_energy(rms)
                    except Exception:
                        pass
                
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(
                        self.jarvis.out_queue.put_nowait,
                        {"data": data, "mime_type": "audio/pcm"}
                    )

        while True:
            try:
                with lazy_sd().InputStream(
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
    async def play_loop(self) -> None:
        """Plays received PCM audio chunks from Gemini Live with low latency & zero stutter."""
        print("[AudioEngine] Play started")
        stream = lazy_sd().RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            latency="low",
        )
        stream.start()

        speaking_timeout_task = None

        async def _reset_speaking_delayed():
            await asyncio.sleep(0.35)
            if self.jarvis.audio_in_queue.empty():
                self.jarvis.set_speaking(False)

        try:
            while True:
                chunk = await self.jarvis.audio_in_queue.get()
                if not chunk:
                    continue

                if speaking_timeout_task and not speaking_timeout_task.done():
                    speaking_timeout_task.cancel()

                self.jarvis.set_speaking(True)

                if hasattr(self.jarvis.ui, "set_speaker_energy"):
                    try:
                        import numpy as np
                        audio_np = np.frombuffer(chunk, dtype=np.int16)
                        rms = np.sqrt(np.mean(np.square(audio_np.astype(np.float32)))) / 32768.0
                        self.jarvis.ui.set_speaker_energy(rms)
                    except Exception:
                        pass

                await asyncio.to_thread(stream.write, chunk)

                if self.jarvis.audio_in_queue.empty():
                    speaking_timeout_task = asyncio.create_task(_reset_speaking_delayed())

        except Exception as e:
            print(f"[AudioEngine] Play error: {e}")
            raise
        finally:
            self.jarvis.set_speaking(False)
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
