# core/audio_engine.py

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
        self.jarvis = jarvis
        self._loop = None

    async def send_realtime_loop(self):
        """Sends audio chunks to the session."""
        while True:
            msg = await self.jarvis.out_queue.get()
            # Block audio during tool calls OR when model is speaking
            with self.jarvis._speaking_lock:
                busy = getattr(self.jarvis, "tool_call_pending", False) or self.jarvis._is_speaking
            
            if busy:
                continue
            if self.jarvis.session:
                try:
                    await self.jarvis.session.send_realtime_input(media=msg)
                except Exception as e:
                    print(f"[AudioEngine] Send error: {e}")

    async def detection_loop(self):
        """Offloaded clap and wake word detection."""
        while True:
            try:
                indata = await self.jarvis.detection_queue.get()
                
                with self.jarvis._speaking_lock:
                    jarvis_speaking = self.jarvis._is_speaking

                if jarvis_speaking:
                    continue

                # Clap Detection
                if self.jarvis.clap_enabled and self.jarvis.detector:
                    if self.jarvis.detector.is_clap(indata):
                        print("[JARVIS] Clap detected!")
                        if self.jarvis.ui.muted:
                            self.jarvis.ui.root.after(0, self.jarvis.ui._toggle_mute)
                        else:
                            self.jarvis.ui.write_log("SYS: Clap detected (Already active).")

                # Wake Word Detection
                if self.jarvis.wake_word_enabled and self.jarvis.wake_detector:
                    if self.jarvis.wake_detector.check(indata):
                        print("[JARVIS] Wake word detected!")
                        if self.jarvis.ui.muted:
                            self.jarvis.ui.root.after(0, self.jarvis.ui._toggle_mute)
                        else:
                            self.jarvis.ui.write_log("SYS: Wake word detected (Already active).")
            except Exception as e:
                print(f"[AudioEngine] Detection error: {e}")
            finally:
                self.jarvis.detection_queue.task_done()

    async def listen_loop(self):
        """Captures microphone audio."""
        print("[AudioEngine] Mic started")
        self._loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            if (self.jarvis.clap_enabled or self.jarvis.wake_word_enabled):
                self._loop.call_soon_threadsafe(self.jarvis.detection_queue.put_nowait, indata.copy())

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

    async def play_loop(self):
        """Plays received audio chunks."""
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
