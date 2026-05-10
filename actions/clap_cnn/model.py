# actions/clap_cnn/model.py
# ══════════════════════════════════════════════════════════════
# JARVIS CNN Clap Detection Model
# 4-layer Convolutional Neural Network on Mel Spectrograms
#
# pip install torch torchvision torchaudio
# ══════════════════════════════════════════════════════════════

import torch
import torch.nn as nn
import torch.nn.functional as F


class AudioClassifier(nn.Module):
    """
    4-layer CNN that classifies audio as 'clap' (1) or 'noise' (0).

    Input:  1-channel mel spectrogram image (1 × 256 × 256)
    Output: log-softmax over 2 classes [noise, clap]

    Architecture:
      Conv2d block × 4 (with BatchNorm + ReLU + MaxPool)
      → Flatten
      → FC(128) + Dropout
      → FC(2) → LogSoftmax
    """

    def __init__(self):
        super().__init__()

        # Block 1: 1 → 32 channels
        self.conv1 = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),          # 256 → 128
        )

        # Block 2: 32 → 64 channels
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),          # 128 → 64
        )

        # Block 3: 64 → 64 channels (no pooling)
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
        )

        # Block 4: 64 → 64 channels + Dropout
        self.conv4 = nn.Sequential(
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Dropout2d(p=0.5),
        )

        # Adaptive pool to fixed 8×8 (handles any input size)
        self.adaptive_pool = nn.AdaptiveAvgPool2d((8, 8))

        # Fully connected layers
        self.fc1 = nn.Sequential(
            nn.Linear(64 * 8 * 8, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.5),
        )
        self.fc2 = nn.Linear(128, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.adaptive_pool(x)
        x = x.view(x.size(0), -1)        # flatten
        x = self.fc1(x)
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)
