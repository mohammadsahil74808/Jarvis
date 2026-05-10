# actions/clap_cnn/train.py
# ══════════════════════════════════════════════════════════════
# JARVIS CNN Clap Detector — Trainer
#
# Run after recording samples:
#   python actions/clap_cnn/train.py
#
# Saves: actions/clap_cnn/clap_model.pth
# Training time: ~2-5 minutes on CPU with 300+300 samples
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchaudio.transforms as T
from torchvision.transforms.functional import resize

from .model import AudioClassifier

DATA_DIR   = Path(__file__).parent / "data"
MODEL_PATH = Path(__file__).parent / "clap_model.pth"
SAMPLE_RATE = 44100
EPOCHS     = 10
BATCH_SIZE = 16
LR         = 1e-3


class ClapDataset(Dataset):
    def __init__(self):
        self.samples = []
        self.labels  = []
        self._mel = T.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=400,
            win_length=400,
            hop_length=200,
            n_mels=128,
        )
        for label, class_name in [(0, "noise"), (1, "clap")]:
            class_dir = DATA_DIR / class_name
            if not class_dir.exists():
                print(f"⚠ No data found in {class_dir}")
                continue
            for f in sorted(class_dir.glob("*.npy")):
                self.samples.append(f)
                self.labels.append(label)
        print(f"Dataset: {len(self.samples)} samples "
              f"({self.labels.count(1)} clap, {self.labels.count(0)} noise)")

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx):
        audio = np.load(self.samples[idx]).astype(np.float32) / 32768.0
        # Pad or trim to exactly 1 second
        target_len = SAMPLE_RATE
        if len(audio) < target_len:
            audio = np.pad(audio, (0, target_len - len(audio)))
        else:
            audio = audio[:target_len]

        waveform = torch.from_numpy(audio).unsqueeze(0)
        spec     = self._mel(waveform)
        # Resize to 256×256
        spec     = resize(spec, [256, 256])
        # Normalize
        mean, std = spec.mean(), spec.std()
        if std > 0:
            spec = (spec - mean) / std
        return spec.unsqueeze(0), self.labels[idx]


def train():
    print("\n" + "="*50)
    print("JARVIS CNN Clap Detector — Training")
    print("="*50 + "\n")

    dataset = ClapDataset()
    if len(dataset) < 10:
        print("✗ Not enough samples. Record at least 50 clap + 50 noise samples first.")
        return

    # 80/20 train/val split
    val_size   = max(1, int(len(dataset) * 0.2))
    train_size = len(dataset) - val_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE)

    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model     = AudioClassifier().to(device)
    criterion = nn.NLLLoss()
    optimizer = optim.Adam(model.parameters(), lr=LR)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.5)

    print(f"Device: {device}")
    print(f"Train: {train_size} | Val: {val_size}")
    print(f"Epochs: {EPOCHS} | Batch: {BATCH_SIZE}\n")

    best_val_acc = 0.0

    for epoch in range(1, EPOCHS + 1):
        # ── Training ──────────────────────────────────────────
        model.train()
        train_loss, train_correct = 0.0, 0
        for specs, labels in train_loader:
            specs, labels = specs.to(device), labels.to(device)
            optimizer.zero_grad()
            output = model(specs)
            loss   = criterion(output, labels)
            loss.backward()
            optimizer.step()
            train_loss    += loss.item()
            train_correct += (output.argmax(1) == labels).sum().item()

        # ── Validation ────────────────────────────────────────
        model.eval()
        val_correct = 0
        with torch.no_grad():
            for specs, labels in val_loader:
                specs, labels = specs.to(device), labels.to(device)
                output      = model(specs)
                val_correct += (output.argmax(1) == labels).sum().item()

        train_acc = train_correct / train_size * 100
        val_acc   = val_correct   / val_size   * 100

        print(f"Epoch {epoch:2d}/{EPOCHS} | "
              f"Loss: {train_loss/len(train_loader):.4f} | "
              f"Train: {train_acc:.1f}% | Val: {val_acc:.1f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"           ✓ Best model saved ({val_acc:.1f}%)")

        scheduler.step()

    print(f"\n{'='*50}")
    print(f"Training complete! Best val accuracy: {best_val_acc:.1f}%")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    train()
