# actions/clap_cnn/dataloader.py
# ══════════════════════════════════════════════════════════════
# JARVIS CNN Clap Detector — Dataset Loader
# Loads WAV files for training the AudioClassifier
# Based on reference implementation, adapted for JARVIS
# ══════════════════════════════════════════════════════════════

import os
import torch
import torchaudio
import torchaudio.transforms as T
from torch.utils.data import Dataset
from torchvision.transforms.functional import resize
from pathlib import Path


def get_wav_files(directory: str) -> list[str]:
    """Return all .wav files in a directory."""
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".wav")
    ]


class AudioDataset(Dataset):
    """
    Dataset that loads WAV files from two folders:
      - noise_dir : label 0 (background noise, knocks, music, etc.)
      - clap_dir  : label 1 (hand claps)

    Each sample is converted to a 256×256 normalized mel spectrogram.

    Usage:
        dataset = AudioDataset(
            noise_dir="actions/clap_cnn/data/wav/noise",
            clap_dir="actions/clap_cnn/data/wav/clap"
        )
    """

    def __init__(
        self,
        noise_dir: str,
        clap_dir:  str,
        n_mels:      int = 128,
        n_fft:       int = 400,
        hop_length:  int = 200,
    ):
        self.n_mels      = n_mels
        self.n_fft       = n_fft
        self.hop_length  = hop_length

        noise_files = get_wav_files(noise_dir) if os.path.isdir(noise_dir) else []
        clap_files  = get_wav_files(clap_dir)  if os.path.isdir(clap_dir)  else []

        if not noise_files:
            print(f"⚠ No noise WAV files found in: {noise_dir}")
        if not clap_files:
            print(f"⚠ No clap WAV files found in: {clap_dir}")

        self.file_list = noise_files + clap_files
        self.labels    = [0] * len(noise_files) + [1] * len(clap_files)

        print(
            f"AudioDataset: {len(self.file_list)} total samples "
            f"({len(clap_files)} clap, {len(noise_files)} noise)"
        )

    def __len__(self) -> int:
        return len(self.file_list)

    def __getitem__(self, idx: int):
        path     = self.file_list[idx]
        label    = self.labels[idx]

        try:
            waveform, sample_rate = torchaudio.load(path)

            # Resample to 44100 if needed
            if sample_rate != 44100:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, new_freq=44100
                )
                waveform    = resampler(waveform)
                sample_rate = 44100

            # Mono (if stereo, take mean)
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)

            # Mel spectrogram
            mel_transform = T.MelSpectrogram(
                sample_rate=sample_rate,
                n_fft=self.n_fft,
                win_length=self.n_fft,
                hop_length=self.hop_length,
                n_mels=self.n_mels,
            )
            spec = mel_transform(waveform)

            # Resize to 256×256
            spec = resize(spec, [256, 256])

            # Normalize
            mean = spec.mean()
            std  = spec.std()
            if std > 0:
                spec = (spec - mean) / std
            else:
                spec = spec - mean

            return spec, torch.tensor(label, dtype=torch.long)

        except Exception as e:
            print(f"⚠ Error loading {path}: {e} — returning zeros")
            return torch.zeros(1, 256, 256), torch.tensor(label, dtype=torch.long)
