# actions/clap_cnn/augment.py
# ══════════════════════════════════════════════════════════════
# JARVIS CNN Clap Detector — Data Augmentation
# Takes recorded WAV samples and creates variations:
#   - Pitch shifts (-2, +2, +5 semitones)
#   - Volume changes (+5, +10, +15 dB)
#   - Noise injection (mild)
#
# Run this AFTER recording samples, BEFORE training:
#   python actions/clap_cnn/augment.py
#
# pip install librosa soundfile pydub
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import os
from pathlib import Path
import numpy as np

DATA_DIR = Path(__file__).parent / "data" / "wav"


def pitch_shift(audio_file: str, semitones: int):
    """Shift pitch by given semitones."""
    import librosa
    import soundfile as sf
    y, sr = librosa.load(audio_file, sr=None)
    y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones)
    return y_shifted, sr


def change_volume(audio_file: str, db_change: int):
    """Increase volume by db_change dB."""
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(audio_file)
    return audio + db_change


def add_noise(audio_file: str, noise_factor: float = 0.002):
    """Add gentle white noise."""
    import librosa
    y, sr = librosa.load(audio_file, sr=None)
    noise = np.random.randn(len(y))
    augmented = y + noise_factor * noise
    augmented = augmented.astype(np.float32)
    return augmented, sr


def augment_folder(class_name: str) -> int:
    """
    Augment all WAV files in a class folder.
    Returns number of new files created.
    """
    import soundfile as sf

    folder = DATA_DIR / class_name
    if not folder.exists():
        print(f"⚠ Folder not found: {folder}")
        return 0

    wav_files = [
        f for f in os.listdir(folder)
        if f.endswith(".wav")
        and "shifted" not in f
        and "volume" not in f
        and "noisy" not in f
    ]

    if not wav_files:
        print(f"⚠ No original WAV files found in {folder}")
        return 0

    print(f"Augmenting {len(wav_files)} '{class_name}' samples...")
    new_count = 0

    for filename in wav_files:
        audio_file = str(folder / filename)
        base_name  = os.path.splitext(filename)[0]

        # ── Pitch shifts ──────────────────────────────────────
        for semitones in [-2, 2, 5]:
            out_name = folder / f"{base_name}_shifted{semitones:+d}.wav"
            if not out_name.exists():
                try:
                    y, sr = pitch_shift(audio_file, semitones)
                    sf.write(str(out_name), y, sr)
                    new_count += 1
                except Exception as e:
                    print(f"  Pitch shift error ({filename}): {e}")

        # ── Volume changes ────────────────────────────────────
        for db in [5, 10, 15]:
            out_name = folder / f"{base_name}_vol{db:+d}db.wav"
            if not out_name.exists():
                try:
                    louder = change_volume(audio_file, db)
                    louder.export(str(out_name), format="wav")
                    new_count += 1
                except Exception as e:
                    print(f"  Volume change error ({filename}): {e}")

        # ── Noise injection ───────────────────────────────────
        out_name = folder / f"{base_name}_noisy.wav"
        if not out_name.exists():
            try:
                y, sr = add_noise(audio_file, noise_factor=0.002)
                sf.write(str(out_name), y, sr)
                new_count += 1
            except Exception as e:
                print(f"  Noise injection error ({filename}): {e}")

    print(f"  ✓ Created {new_count} augmented samples for '{class_name}'")
    return new_count


def augment_all():
    """Augment both clap and noise folders."""
    print("\n" + "="*50)
    print("JARVIS CNN — Data Augmentation")
    print("="*50 + "\n")

    total = 0
    for class_name in ["clap", "noise"]:
        total += augment_folder(class_name)

    print(f"\n✓ Total new augmented samples: {total}")
    print("Now run: python -c \"from actions.clap_cnn.train import train; train()\"")


if __name__ == "__main__":
    augment_all()
