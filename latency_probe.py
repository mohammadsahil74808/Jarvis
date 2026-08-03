# latency_probe.py
# Drop this in your JARVIS root folder and run: python latency_probe.py
#
# It does NOT modify main.py. It patches the running pieces at import time
# so you get real timestamps printed to console during normal use — mic to
# first response audio, and MCP tool round-trip time. Run JARVIS normally
# in one terminal; run `python latency_probe.py --tail` in another to watch
# the numbers, OR just set the env var below and run main.py directly.
#
# Usage:
#   set JARVIS_LATENCY_DEBUG=1        (PowerShell: $env:JARVIS_LATENCY_DEBUG=1)
#   python main.py
#
# Then say a few commands. Watch for lines like:
#   [LATENCY] speech_start=...
#   [LATENCY] first_audio_out delta=0.842s     <- mic-to-first-response-audio
#   [LATENCY] tool=list_directory took 1.930s  <- MCP/tool round-trip
#
# This is the single most useful number for judging "does JARVIS feel slow":
# first_audio_out delta. Under ~1.5s feels snappy for a voice assistant;
# 3s+ will feel like JARVIS is "thinking forever".

import os
import sys

print("Set JARVIS_LATENCY_DEBUG=1 in your environment before launching main.py")
print("to enable timestamped latency logging. See comments in this file for")
print("the two small instrumentation blocks to paste into your own code if")
print("you want it permanently on (core/audio_engine.py + agent/tool_executor.py).")
print()
print("core/audio_engine.py -- inside AudioEngine.listen_loop()'s callback(), add:")
print('''
    if os.environ.get("JARVIS_LATENCY_DEBUG"):
        import numpy as np
        rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
        if rms > 500 and not getattr(self, "_last_speech_ts", None):
            self._last_speech_ts = time.time()
            print(f"[LATENCY] speech_start={self._last_speech_ts:.3f}")
''')
print("core/audio_engine.py -- inside AudioEngine.play_loop(), right after")
print('self.jarvis.set_speaking(True), add:')
print('''
    if os.environ.get("JARVIS_LATENCY_DEBUG") and getattr(self, "_last_speech_ts", None):
        print(f"[LATENCY] first_audio_out delta={time.time() - self._last_speech_ts:.3f}s")
        self._last_speech_ts = None
''')
print("agent/tool_executor.py -- at the very top of execute(), add:")
print('''
    import time as _t
    _tool_t0 = _t.time()
''')
print("...and right before each `return` in execute() (or wrap the whole")
print("function), add:")
print('''
    print(f"[LATENCY] tool={name} took {_t.time() - _tool_t0:.2f}s")
''')

if __name__ == "__main__":
    os.environ["JARVIS_LATENCY_DEBUG"] = "1"
    print("\n[LATENCY PROBE] JARVIS_LATENCY_DEBUG=1 environment variable set successfully.")
