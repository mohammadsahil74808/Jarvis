import numpy as np
import time

class ClapDetector:
    """
    Utility class to detect sharp sound spikes (claps) in an audio stream.
    """
    def __init__(self, threshold=18000, ratio=6.0, cooldown=1.2):
        """
        :param threshold: Minimum absolute amplitude (for int16, max is 32767).
        :param ratio: How many times larger the peak must be than the mean (spike factor).
        :param cooldown: Minimum seconds between clap detections.
        """
        self.threshold = threshold
        self.ratio = ratio
        self.cooldown = cooldown
        self.last_clap_time = 0

    def is_clap(self, indata):
        """
        Analyzes a chunk of audio to see if it qualifies as a clap.
        :param indata: numpy array of the current audio chunk.
        :return: True if a clap is detected.
        """
        if indata.size == 0:
            return False

        # Work with absolute values
        abs_data = np.abs(indata)
        peak = np.max(abs_data)

        # 1. Must be loud enough
        if peak < self.threshold:
            return False

        # 2. Must be a sharp spike (Peak to Mean Ratio)
        avg = np.mean(abs_data)
        if avg == 0 or (peak / avg) < self.ratio:
            return False

        # 3. Cooldown check
        now = time.time()
        if now - self.last_clap_time < self.cooldown:
            return False

        self.last_clap_time = now
        return True
