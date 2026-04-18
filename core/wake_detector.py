import os
import json
import logging
from vosk import Model, KaldiRecognizer

# Disable Vosk logs to keep cleaning output
import vosk
vosk.SetLogLevel(-1)

class WakeWordDetector:
    """
    Utility class to detect a specific wake word using Vosk offline STT.
    """
    def __init__(self, model_path, keyword="jarvis", sample_rate=16000):
        """
        :param model_path: Path to the Vosk model directory.
        :param keyword: The keyword to listen for.
        :param sample_rate: Audio sample rate (must match the input stream).
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at {model_path}. Please ensure it is downloaded and extracted.")
        
        self.model = Model(model_path)
        self.rec = KaldiRecognizer(self.model, sample_rate)
        self.keyword = keyword.lower()
        self.sample_rate = sample_rate

    def check(self, audio_data):
        """
        Analyzes a chunk of audio to see if the wake word is mentioned.
        :param audio_data: numpy array or bytes of the current audio chunk.
        :return: True if the wake word is detected.
        """
        if isinstance(audio_data, bytes):
            data = audio_data
        else:
            # Convert numpy array (int16) to bytes
            data = audio_data.tobytes()

        # Check partial results for faster activation
        if self.rec.AcceptWaveform(data):
            result = json.loads(self.rec.Result())
            text = result.get("text", "").lower()
            if self.keyword in text:
                return True
        else:
            partial = json.loads(self.rec.PartialResult())
            text = partial.get("partial", "").lower()
            # We look for the keyword in the partial result
            # We check if the last word or the whole partial contains the keyword
            if self.keyword in text:
                # Reset the recognizer after detection to avoid duplicate triggers
                self.rec.Reset()
                return True
        
        return False
