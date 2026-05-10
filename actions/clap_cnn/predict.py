# actions/clap_cnn/predict.py
# ══════════════════════════════════════════════════════════════
# JARVIS CNN Clap Detector — Prediction Helper
# Test your trained model on individual audio files
#
# Run:
#   python actions/clap_cnn/predict.py --file path/to/audio.wav
#   python actions/clap_cnn/predict.py --test   (runs live test)
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import argparse
from pathlib import Path
import torch
import torchaudio
import torchaudio.transforms as T
from torchvision.transforms.functional import resize

# Default model path
MODEL_PATH = Path(__file__).parent / "clap_model.pth"
SAMPLE_RATE = 44100


def load_model(model_path: Path = MODEL_PATH):
    """Load trained AudioClassifier from .pth file."""
    from actions.clap_cnn.model import AudioClassifier
    model = AudioClassifier()
    model.load_state_dict(
        torch.load(str(model_path), map_location="cpu", weights_only=True)
    )
    model.eval()
    return model


def transform_audio(
    audio_path: str,
    n_mels:     int = 128,
    n_fft:      int = 400,
    hop_length: int = 200,
) -> torch.Tensor:
    """
    Load a WAV file and convert to normalized mel spectrogram tensor.
    Returns shape: [1, 1, 256, 256]  (batch=1, channels=1, H=256, W=256)
    """
    waveform, sr = torchaudio.load(audio_path)

    # Resample if needed
    if sr != SAMPLE_RATE:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=SAMPLE_RATE)
        waveform  = resampler(waveform)

    # Mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Mel spectrogram
    spec = T.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=n_fft,
        win_length=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
    )(waveform)

    # Resize to 256×256
    spec = resize(spec, [256, 256])

    # Normalize
    mean, std = spec.mean(), spec.std()
    if std > 0:
        spec = (spec - mean) / std

    return spec.unsqueeze(0)   # add batch dim


def predict_file(model, audio_path: str) -> tuple[str, float]:
    """
    Predict class for a single WAV file.
    Returns: (class_name, confidence_percent)
    """
    spec   = transform_audio(audio_path)
    with torch.no_grad():
        output       = model(spec)
        probs        = torch.softmax(output, dim=1)
        pred_class   = torch.argmax(output, dim=1).item()
        confidence   = probs[0][pred_class].item() * 100

    class_name = "CLAP 👏" if pred_class == 1 else "Noise 🔇"
    return class_name, confidence


def run_live_test(model, duration_seconds: int = 30):
    """
    Run live microphone test — listens and predicts every 0.5s.
    Exactly like reference live.py but integrated for JARVIS.
    """
    import sounddevice as sd
    import numpy as np
    from scipy.io.wavfile import write as wav_write
    from collections import deque
    import tempfile, os, time

    CHUNK_DURATION  = 0.5   # seconds per chunk
    BUFFER_DURATION = 1.0   # rolling buffer size
    CHUNK_SAMPLES   = int(CHUNK_DURATION  * SAMPLE_RATE)
    BUFFER_SAMPLES  = int(BUFFER_DURATION * SAMPLE_RATE)
    CONFIDENCE_THRESHOLD = 0.99

    print(f"\n🎤 Live test started ({duration_seconds}s). Clap to test!")
    print("   CNN threshold: 99% confidence\n")

    buffer      = deque(maxlen=BUFFER_SAMPLES)
    tmp_file    = tempfile.mktemp(suffix=".wav")
    clap_count  = 0
    iterations  = int(duration_seconds / CHUNK_DURATION)

    with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, dtype="int16") as stream:
        for i in range(iterations):
            chunk, _ = stream.read(CHUNK_SAMPLES)
            buffer.extend(chunk.flatten())

            if len(buffer) < BUFFER_SAMPLES:
                print(".", end="", flush=True)
                continue

            # Save buffer to temp WAV
            wav_write(tmp_file, SAMPLE_RATE, np.array(buffer, dtype="int16"))

            try:
                spec = transform_audio(tmp_file)
                with torch.no_grad():
                    output = model(spec)
                    probs  = torch.softmax(output, dim=1)
                    pred   = torch.argmax(output, dim=1).item()
                    conf   = probs[0][pred].item()

                if pred == 1 and conf >= CONFIDENCE_THRESHOLD:
                    print(f"\n  👏 CLAP DETECTED! ({conf*100:.1f}%)")
                    clap_count += 1
                else:
                    print(".", end="", flush=True)
            except Exception as e:
                print(f"x", end="", flush=True)

            time.sleep(CHUNK_DURATION)

    if os.path.exists(tmp_file):
        os.remove(tmp_file)

    print(f"\n\n✓ Live test complete. Claps detected: {clap_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS CNN Clap Predictor")
    parser.add_argument("--file",  type=str,  help="Path to WAV file to predict")
    parser.add_argument("--test",  action="store_true", help="Run live mic test")
    parser.add_argument("--model", type=str,  default=str(MODEL_PATH),
                        help="Path to .pth model file")
    parser.add_argument("--duration", type=int, default=30,
                        help="Live test duration in seconds")
    args = parser.parse_args()

    if not Path(args.model).exists():
        print(f"✗ Model not found: {args.model}")
        print("  Train first: python -c \"from actions.clap_cnn.train import train; train()\"")
        exit(1)

    print(f"Loading model from: {args.model}")
    model = load_model(Path(args.model))
    print("✓ Model loaded\n")

    if args.file:
        class_name, conf = predict_file(model, args.file)
        print(f"File   : {args.file}")
        print(f"Result : {class_name}")
        print(f"Conf   : {conf:.1f}%")

    elif args.test:
        run_live_test(model, duration_seconds=args.duration)

    else:
        parser.print_help()
