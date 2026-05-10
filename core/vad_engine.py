# core/vad_engine.py
# ══════════════════════════════════════════════════════════════
# JARVIS WebRTC VAD Engine
# Google's production-grade Voice Activity Detection
# Replaces the simple amplitude-based approach in audio_engine.py
#
# pip install webrtcvad
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import collections
import threading
import time
from typing import Callable, Optional
import numpy as np


class VADEngine:
    """
    WebRTC-based voice activity detector.

    How it works:
    1. Receives 10ms PCM chunks from microphone
    2. Google's WebRTC VAD checks if chunk contains speech
    3. Uses 2-frame history to smooth out false triggers
    4. Accumulates voiced frames into a buffer
    5. When silence detected for 'sensitivity' seconds → fires callback

    Used in:  audio_engine.py → detection_loop()
    Replaces: raw amplitude check that triggered on music/knocks
    """

    def __init__(
        self,
        on_speech_end: Callable[[np.ndarray], None],
        sample_rate: int = 16000,
        aggressiveness: int = 3,
        sensitivity: float = 0.4,
    ):
        """
        Parameters
        ----------
        on_speech_end   : callback(audio_np) called when speech segment ends
        sample_rate     : must be 8000, 16000, 32000, or 48000
        aggressiveness  : 0 (least) to 3 (most aggressive noise rejection)
                          mode 3 is best for home/office with background noise
        sensitivity     : seconds of silence before speech is considered ended
        """
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(aggressiveness)
        except ImportError:
            raise ImportError(
                "webrtcvad not installed. Run: pip install webrtcvad"
            )

        self.sample_rate   = sample_rate
        self.sensitivity   = sensitivity
        self._callback     = on_speech_end

        # 10ms chunk = sample_rate / 100 samples × 2 bytes (int16)
        self._chunk_ms     = 10
        self._chunk_samples = int(sample_rate * self._chunk_ms / 1000)
        self._chunk_bytes   = self._chunk_samples * 2  # int16 = 2 bytes each

        # Rolling frame buffer — max 10 seconds of audio
        self._frames: collections.deque = collections.deque(
            maxlen=int(1000 / self._chunk_ms) * 10
        )

        # How many silent chunks before we call it "end of speech"
        self._silence_threshold = int(sensitivity * 1000 / self._chunk_ms)
        self._silent_chunks     = 0
        self._in_speech         = False

        # 2-frame history for smoothing (prevents single-frame false triggers)
        self._history = collections.deque([False, False], maxlen=2)

        # Thread safety
        self._lock    = threading.Lock()
        self._enabled = True

        # Stats
        self.frames_processed = 0
        self.speech_segments  = 0

    # ─────────────────────────────────────────────────────────
    def process_chunk(self, raw_bytes: bytes) -> None:
        """
        Main entry point. Call with each PCM chunk from microphone.
        raw_bytes must be exactly _chunk_bytes long (10ms of int16 audio).
        If your chunks are larger, use process_large_chunk() instead.
        """
        if not self._enabled:
            return

        if len(raw_bytes) != self._chunk_bytes:
            # Wrong size — use the large chunk handler
            self.process_large_chunk(raw_bytes)
            return

        with self._lock:
            self._process_single_chunk(raw_bytes)

    def process_large_chunk(self, raw_bytes: bytes) -> None:
        """
        Splits a larger audio chunk into 10ms pieces and processes each.
        Use this when your CHUNK_SIZE > 10ms worth of audio.
        """
        if not self._enabled:
            return
        # Split into 10ms pieces
        for i in range(0, len(raw_bytes) - self._chunk_bytes + 1, self._chunk_bytes):
            chunk = raw_bytes[i : i + self._chunk_bytes]
            if len(chunk) == self._chunk_bytes:
                with self._lock:
                    self._process_single_chunk(chunk)

    def _process_single_chunk(self, raw_bytes: bytes) -> None:
        """Internal: process exactly one 10ms chunk."""
        self.frames_processed += 1

        try:
            is_speech = self._vad.is_speech(raw_bytes, self.sample_rate)
        except Exception:
            is_speech = False

        # 2-frame smoothing: only count as speech if BOTH current AND previous are speech
        # This eliminates single-frame false triggers (table knock, cough, etc.)
        smoothed_speech = is_speech and self._history[-1]
        self._history.append(is_speech)

        if smoothed_speech:
            # Confirmed speech — accumulate frames
            self._frames.append(raw_bytes)
            self._silent_chunks = 0

            if not self._in_speech:
                self._in_speech = True

        elif self._in_speech:
            # We were in speech but current chunk is silent
            self._silent_chunks += 1
            self._frames.append(raw_bytes)  # keep trailing frames for context

            if self._silent_chunks >= self._silence_threshold:
                # Speech has ended → fire callback
                self._fire_callback()

    def _fire_callback(self) -> None:
        """Assemble accumulated frames and call on_speech_end."""
        if not self._frames:
            self._reset()
            return

        # Concatenate all bytes → numpy int16 array
        raw = b"".join(self._frames)
        audio = np.frombuffer(raw, dtype=np.int16).copy()

        self.speech_segments += 1
        self._reset()

        # Fire callback on a daemon thread so VAD loop isn't blocked
        threading.Thread(
            target=self._callback,
            args=(audio,),
            daemon=True
        ).start()

    def _reset(self) -> None:
        """Reset state after speech segment ends."""
        self._frames.clear()
        self._silent_chunks = 0
        self._in_speech     = False

    def enable(self)  -> None: self._enabled = True
    def disable(self) -> None: self._enabled = False

    @property
    def is_in_speech(self) -> bool:
        return self._in_speech

    def get_stats(self) -> dict:
        return {
            "frames_processed": self.frames_processed,
            "speech_segments":  self.speech_segments,
            "in_speech":        self._in_speech,
            "mode":             self._vad.mode if hasattr(self._vad, "mode") else 3,
        }
