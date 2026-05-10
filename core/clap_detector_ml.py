# core/clap_detector_ml.py
# ══════════════════════════════════════════════════════════════
# JARVIS ML-Powered Clap Detector
# Drop-in replacement for core/clap_detector.py
#
# BEFORE using this file:
# 1. Record samples:  python actions/clap_cnn/record_samples.py --class clap --count 300
#                     python actions/clap_cnn/record_samples.py --class noise --count 300
# 2. Train model:     python actions/clap_cnn/train.py
# 3. Confirm file:    actions/clap_cnn/clap_model.pth exists
#
# Then in core/config.py (or wherever ClapDetector is imported),
# replace 'from core.clap_detector import ClapDetector'
# with    'from core.clap_detector_ml import MLClapDetector as ClapDetector'
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import threading
import time
import collections
from pathlib import Path
from typing import Optional, Callable
import numpy as np

# Model path relative to this file
_DEFAULT_MODEL = Path(__file__).parent.parent / "actions" / "clap_cnn" / "clap_model.pth"

# 99%+ confidence threshold — virtually zero false positives
_CONFIDENCE_THRESHOLD = 0.99

SAMPLE_RATE    = 44100
BUFFER_SECONDS = 1.0


class MLClapDetector:
    """
    CNN-based clap detector using trained AudioClassifier.

    Drop-in replacement for the heuristic ClapDetector.
    Same interface: call is_clap(indata) → True/False

    If model file not found, automatically falls back to
    the original heuristic method so JARVIS still works.

    Parameters
    ----------
    model_path : Path to trained .pth file (auto-detected if None)
    cooldown   : Minimum seconds between detections
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        cooldown: float = 1.5,
        # Legacy params for backward compat with old ClapDetector
        threshold: int = 18000,
        ratio: float = 6.0,
    ):
        self.cooldown       = cooldown
        self.last_clap_time = 0.0
        self._model         = None
        self._model_path    = model_path or _DEFAULT_MODEL
        self._ready         = False
        self._use_fallback  = False

        # Fallback heuristic params
        self._threshold = threshold
        self._ratio     = ratio

        # Rolling 1-second buffer of audio
        self._buffer = collections.deque(
            maxlen=int(SAMPLE_RATE * BUFFER_SECONDS)
        )

        # Pre-compute mel transform once
        self._mel_transform = None

        # Load model in background (non-blocking)
        threading.Thread(target=self._load_model, daemon=True).start()

    # ─────────────────────────────────────────────────────────
    def _load_model(self) -> None:
        """Load CNN model. Falls back to heuristic if unavailable."""
        try:
            import torch
            from actions.clap_cnn.model import AudioClassifier
            import torchaudio.transforms as T

            if not self._model_path.exists():
                print(
                    f"[MLClap] Model not found at {self._model_path}\n"
                    f"         Using heuristic fallback.\n"
                    f"         To train: see actions/clap_cnn/train.py"
                )
                self._use_fallback = True
                return

            m = AudioClassifier()
            m.load_state_dict(
                torch.load(str(self._model_path),
                           map_location="cpu",
                           weights_only=True)
            )
            m.eval()
            self._model = m

            self._mel_transform = T.MelSpectrogram(
                sample_rate=SAMPLE_RATE,
                n_fft=400,
                win_length=400,
                hop_length=200,
                n_mels=128,
            )
            self._ready = True
            print(f"[MLClap] ✓ CNN model loaded ({self._model_path.name})")

        except ImportError as e:
            print(f"[MLClap] Missing dependency: {e}. Using heuristic fallback.")
            self._use_fallback = True
        except Exception as e:
            print(f"[MLClap] Load error: {e}. Using heuristic fallback.")
            self._use_fallback = True

    # ─────────────────────────────────────────────────────────
    def is_clap(self, indata: np.ndarray) -> bool:
        """
        Main detection method — same interface as old ClapDetector.

        Parameters
        ----------
        indata : numpy array of audio chunk (int16, any shape)

        Returns
        -------
        True if a clap was detected with >= 99% confidence
        """
        if indata is None or indata.size == 0:
            return False

        # Cooldown check first (cheap)
        now = time.time()
        if now - self.last_clap_time < self.cooldown:
            return False

        # Fallback to heuristic if model not available
        if self._use_fallback or not self._ready:
            return self._heuristic_check(indata)

        # Add to rolling buffer
        flat = indata.flatten()
        self._buffer.extend(flat)

        # Need at least 1 second of audio
        if len(self._buffer) < int(SAMPLE_RATE * BUFFER_SECONDS):
            return False

        # Run CNN inference
        detected, confidence = self._cnn_predict()

        if detected:
            self.last_clap_time = now
            print(f"[MLClap] 👏 Clap detected! ({confidence*100:.1f}% confidence)")
            return True

        return False

    def _cnn_predict(self) -> tuple[bool, float]:
        """Run CNN on current buffer. Returns (is_clap, confidence)."""
        try:
            import torch
            from torchvision.transforms.functional import resize

            buf = np.array(self._buffer, dtype=np.int16)

            # int16 → float32 normalized
            audio_f32 = buf.astype(np.float32) / 32768.0
            waveform  = torch.from_numpy(audio_f32).unsqueeze(0)

            # Mel spectrogram
            spec = self._mel_transform(waveform)
            spec = resize(spec, [256, 256])

            # Normalize
            mean, std = spec.mean(), spec.std()
            if std > 0:
                spec = (spec - mean) / std

            spec = spec.unsqueeze(0)  # add batch dim → [1,1,256,256]

            with torch.no_grad():
                output = self._model(spec)
                probs  = torch.exp(output)         # log_softmax → probs
                pred   = torch.argmax(output, dim=1).item()
                conf   = probs[0][pred].item()

            return (pred == 1 and conf >= _CONFIDENCE_THRESHOLD), conf

        except Exception as e:
            print(f"[MLClap] Inference error: {e}")
            return False, 0.0

    def _heuristic_check(self, indata: np.ndarray) -> bool:
        """Original amplitude heuristic as fallback."""
        abs_data = np.abs(indata)
        peak = np.max(abs_data)
        if peak < self._threshold:
            return False
        avg = np.mean(abs_data)
        if avg == 0 or (peak / avg) < self._ratio:
            return False
        self.last_clap_time = time.time()
        return True

    @property
    def is_ml_active(self) -> bool:
        """True if CNN model is loaded and active."""
        return self._ready and not self._use_fallback
