# core/whisper_fallback.py
# ══════════════════════════════════════════════════════════════
# JARVIS Whisper Offline STT Fallback
# Activates ONLY when Gemini Live session is disconnected
#
# pip install openai-whisper
# Model downloads automatically on first use:
#   tiny.en  = 74 MB  (fastest, less accurate)
#   base.en  = 145 MB (recommended — good balance)
#   small.en = 461 MB (most accurate, slower)
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import threading
import time
from typing import Optional
import numpy as np


# Phrases that Whisper hallucinates when given silence or noise
_HALLUCINATION_PHRASES = [
    "thank you for watching",
    "please subscribe",
    "subtitles by",
    "transcribed by",
    "translation by",
    "like and subscribe",
    "www.",
    ".com",
    "amara.org",
    "subdigest",
    "♪",
]


class WhisperFallback:
    """
    Local Whisper-based STT that runs when Gemini Live is offline.

    Usage:
        # In main.py __init__:
        self.whisper_fb = WhisperFallback(model_size="base.en")

        # After startup (non-blocking warm-up):
        threading.Thread(target=self.whisper_fb.warm_up, daemon=True).start()

        # In run() — when session is None (disconnected):
        if self.whisper_fb.is_ready:
            text = self.whisper_fb.transcribe(audio_numpy_array)
            if text:
                self._on_text_command(text)
    """

    _model = None          # shared across instances (loaded once)
    _model_lock = threading.Lock()

    def __init__(self, model_size: str = "base.en"):
        """
        model_size: "tiny.en" | "base.en" | "small.en"
                    ".en" suffix = English-only, faster than multilingual
        """
        self.model_size   = model_size
        self._ready       = False
        self._load_error  = None

    # ─────────────────────────────────────────────────────────
    def warm_up(self) -> None:
        """
        Load the Whisper model in background.
        Call this in a daemon thread right after JARVIS starts.
        Does NOT block the main thread.
        """
        with WhisperFallback._model_lock:
            if WhisperFallback._model is not None:
                self._ready = True
                return
            try:
                import whisper
                print(f"[WhisperFallback] Loading '{self.model_size}' model...")
                t0 = time.time()
                WhisperFallback._model = whisper.load_model(self.model_size)
                elapsed = time.time() - t0
                self._ready = True
                print(f"[WhisperFallback] ✓ Ready in {elapsed:.1f}s")
            except ImportError:
                self._load_error = (
                    "openai-whisper not installed. "
                    "Run: pip install openai-whisper"
                )
                print(f"[WhisperFallback] ⚠ {self._load_error}")
            except Exception as e:
                self._load_error = str(e)
                print(f"[WhisperFallback] ✗ Load failed: {e}")

    # ─────────────────────────────────────────────────────────
    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "en",
    ) -> Optional[str]:
        """
        Transcribe audio using local Whisper model.

        Parameters
        ----------
        audio    : int16 numpy array (from sounddevice or PyAudio)
        language : ISO language code (default "en")

        Returns
        -------
        Transcribed text string, or None if failed / hallucination detected
        """
        if not self._ready or WhisperFallback._model is None:
            return None

        if audio is None or len(audio) == 0:
            return None

        try:
            # Convert int16 [-32768, 32767] → float32 [-1.0, 1.0]
            audio_f32 = audio.astype(np.float32) / 32768.0

            # Whisper needs at least 0.1s of audio
            if len(audio_f32) < 1600:  # 0.1s @ 16kHz
                return None

            result = WhisperFallback._model.transcribe(
                audio_f32,
                language=language,
                # ── Multi-temperature fallback (reference pattern) ──
                # Tries temperature 0.0 first (deterministic + no repetition)
                # Escalates only if quality metrics fail
                temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
                # Quality thresholds — trigger fallback to higher temp:
                compression_ratio_threshold=2.4,   # > 2.4 = repetitive output
                logprob_threshold=-1.0,             # < -1.0 = too uncertain
                no_speech_threshold=0.6,            # > 0.6 = probably silence
                # Disable initial timestamp (speeds up short clips)
                without_timestamps=True,
                # Beam search off for speed (greedy decoding)
                beam_size=None,
                best_of=None,
                fp16=False,  # CPU compatibility
            )

            text = result.get("text", "").strip()

            if not text or len(text) < 2:
                return None

            # ── Hallucination filter ─────────────────────────────────
            text_lower = text.lower()
            for phrase in _HALLUCINATION_PHRASES:
                if phrase in text_lower:
                    print(f"[WhisperFallback] Hallucination filtered: '{text[:60]}'")
                    return None

            # Filter very short repeated characters (e.g. "aaaaaaa")
            if len(set(text.lower().replace(" ", ""))) < 3:
                return None

            print(f"[WhisperFallback] Transcribed: '{text}'")
            return text

        except Exception as e:
            print(f"[WhisperFallback] Transcription error: {e}")
            return None

    # ─────────────────────────────────────────────────────────
    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def error(self) -> Optional[str]:
        return self._load_error

    def __repr__(self) -> str:
        status = "ready" if self._ready else ("error" if self._load_error else "loading")
        return f"WhisperFallback(model={self.model_size}, status={status})"
