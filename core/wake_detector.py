# core/wake_detector.py
# ══════════════════════════════════════════════════════════════
# JARVIS openWakeWord-powered Keyword Detector
# Ultra-lightweight, extremely accurate, and 100% offline.
# Replaces the massive Vosk ASR engine.
# ══════════════════════════════════════════════════════════════

import numpy as np
import collections
from openwakeword.model import Model

class WakeWordDetector:
    """
    Utility class to detect 'Hey Jarvis' using openWakeWord (ONNX-based).
    Very lightweight, fast, and high-accuracy replacement for Vosk.
    """
    def __init__(self, model_path=None, keyword="hey_jarvis", sample_rate=16000):
        """
        :param model_path: Kept for backward compatibility with main.py signature, but unused.
        :param keyword: The keyword model to listen for.
        :param sample_rate: Audio sample rate (must match the input stream).
        """
        # Enforce ONNX runtime so tflite-runtime dependency is not needed
        self.oww = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx"
        )
        self.buffer = collections.deque(maxlen=4800)
        self.keyword = "hey_jarvis"
        self.sample_rate = sample_rate

    def check(self, audio_data) -> bool:
        """
        Analyzes a chunk of audio to see if the wake word is mentioned.
        :param audio_data: numpy array or bytes of the current audio chunk.
        :return: True if the wake word is detected.
        """
        if audio_data is None:
            return False

        # Convert to flat list of values for fast buffer extensions
        if isinstance(audio_data, bytes):
            flat = np.frombuffer(audio_data, dtype=np.int16).tolist()
        else:
            flat = audio_data.flatten().tolist()

        self.buffer.extend(flat)

        detected = False
        # openWakeWord handles its own temporal context; we just feed it non-overlapping 1280-sample chunks (80ms)
        chunk_size = 1280
        while len(self.buffer) >= chunk_size:
            # Extract exactly one chunk and remove it from the deque
            chunk = np.array([self.buffer.popleft() for _ in range(chunk_size)], dtype=np.int16)
            
            # Get predictions
            prediction = self.oww.predict(chunk)
            score = prediction.get(self.keyword, 0.0)

            # Default threshold for hey_jarvis is 0.5
            if score >= 0.5:
                detected = True
                self.buffer.clear()  # Reset buffer to avoid multi-trigger feedback
                break

        return detected
