# actions/clap_cnn/record_samples.py
# ══════════════════════════════════════════════════════════════
# JARVIS CNN Clap Detector — Training Data Recorder
#
# Run this ONCE to record training samples:
#   python actions/clap_cnn/record_samples.py --class clap --count 300
#   python actions/clap_cnn/record_samples.py --class noise --count 300
#
# pip install sounddevice numpy
# ══════════════════════════════════════════════════════════════

import argparse
import os
import time
from pathlib import Path
import numpy as np
import sounddevice as sd

SAMPLE_RATE  = 44100
DURATION     = 1.0          # 1 second per sample
CHANNELS     = 1
DATA_DIR     = Path(__file__).parent / "data"


def record_samples(class_name: str, count: int):
    save_dir = DATA_DIR / class_name
    save_dir.mkdir(parents=True, exist_ok=True)

    existing = len(list(save_dir.glob("*.npy")))
    print(f"\n{'='*50}")
    print(f"Recording class: '{class_name}'")
    print(f"Existing samples: {existing}")
    print(f"New samples to record: {count}")
    print(f"Save directory: {save_dir}")
    print(f"{'='*50}\n")

    if class_name == "clap":
        print("Instructions: CLAP once after each beep.")
    else:
        print("Instructions: Stay quiet / make background noise after each beep.")

    input("Press ENTER to start recording...\n")

    recorded = 0
    while recorded < count:
        idx = existing + recorded
        print(f"  [{recorded+1}/{count}] Recording in 0.5s...", end="", flush=True)
        time.sleep(0.5)

        # Beep via print (visual indicator)
        print(" ► Recording...", end="", flush=True)

        audio = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
        )
        sd.wait()

        save_path = save_dir / f"{class_name}_{idx:04d}.npy"
        np.save(save_path, audio.flatten())
        print(f" ✓ Saved ({save_path.name})")
        recorded += 1

    print(f"\n✓ Done! Recorded {count} '{class_name}' samples.")
    print(f"Total '{class_name}' samples: {existing + count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record CNN training samples")
    parser.add_argument("--class", dest="class_name",
                        choices=["clap", "noise"], required=True)
    parser.add_argument("--count", type=int, default=300)
    args = parser.parse_args()
    record_samples(args.class_name, args.count)
