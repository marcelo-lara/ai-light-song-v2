from __future__ import annotations

import json
import logging
from pathlib import Path

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

EVENT_TYPES = [
    "build",
    "breakdown",
    "drop",
    "fake_drop",
    "pause_break",
    "vocal_tail",
    "energy_reset",
    "drop_explode",
    "drop_groove",
    "drop_punch",
    "soft_release",
    "anthem_call",
    "call_response",
    "hook_phrase",
    "vocal_spotlight",
    "no_drop_plateau",
    "tension_hold",
    "groove_loop",
    "atmospheric_plateau",
    "percussion_break",
    "instrumental_bed",
    "layer_add",
    "layer_remove",
    "impact_hit",
    "stinger",
    "heartbeat_pattern",
    "four_on_the_floor",
]

EVENT_TYPE_TO_IDX = {name: i for i, name in enumerate(EVENT_TYPES)}
NUM_CLASSES = len(EVENT_TYPES)


class Event1DCNN(nn.Module):
    def __init__(self, num_features: int, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.conv1 = nn.Conv1d(num_features, 64, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(64)
        self.relu1 = nn.LeakyReLU(0.1)
        self.pool1 = nn.MaxPool1d(2)

        self.conv2 = nn.Conv1d(64, 128, kernel_size=5, padding=2)
        self.bn2 = nn.BatchNorm1d(128)
        self.relu2 = nn.LeakyReLU(0.1)
        self.pool2 = nn.MaxPool1d(2)

        self.conv3 = nn.Conv1d(128, 256, kernel_size=9, padding=4)
        self.bn3 = nn.BatchNorm1d(256)
        self.relu3 = nn.LeakyReLU(0.1)
        self.pool3 = nn.AdaptiveMaxPool1d(1)

        self.fc_head = nn.Sequential(
            nn.Linear(256, 128),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input shape: (batch, channels, seq_len)
        x = self.pool1(self.relu1(self.bn1(self.conv1(x))))
        x = self.pool2(self.relu2(self.bn2(self.conv2(x))))
        x = self.pool3(self.relu3(self.bn3(self.conv3(x))))
        x = x.view(x.size(0), -1)
        return self.fc_head(x)


def _ordered_feature_keys(row: dict) -> list[str]:
    keys: list[str] = []

    normalized = row.get("normalized", {})
    keys.extend(f"norm_{name}" for name in sorted(normalized.keys()))

    derived = row.get("derived", {})
    keys.extend(f"deriv_{name}" for name in sorted(derived.keys()))

    rolling = row.get("rolling", {})
    for scale in sorted(rolling.keys()):
        window = rolling.get(scale, {})
        keys.extend(f"roll_{scale}_{name}" for name in sorted(window.keys()))

    return keys


def parse_contextual_features(filepath: Path) -> tuple[torch.Tensor, dict[int, float], list[str]]:
    if not filepath.exists():
        return torch.empty(0), {}, []

    with filepath.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    records = data.get("features", [])
    if not records:
        return torch.empty(0), {}, []

    keys = _ordered_feature_keys(records[0])
    num_features = len(keys)
    sequence_length = len(records)

    if num_features == 0:
        return torch.empty(0), {}, []

    tensor = torch.zeros((num_features, sequence_length), dtype=torch.float32)
    times: dict[int, float] = {}

    for row_index, row in enumerate(records):
        times[row_index] = float(row.get("time_s", row.get("time", round(row_index * 0.1, 6))))

        feature_index = 0

        normalized = row.get("normalized", {})
        for name in sorted(normalized.keys()):
            tensor[feature_index, row_index] = float(normalized.get(name, 0.0))
            feature_index += 1

        derived = row.get("derived", {})
        for name in sorted(derived.keys()):
            tensor[feature_index, row_index] = float(derived.get(name, 0.0))
            feature_index += 1

        rolling = row.get("rolling", {})
        for scale in sorted(rolling.keys()):
            window = rolling.get(scale, {})
            for name in sorted(window.keys()):
                tensor[feature_index, row_index] = float(window.get(name, 0.0))
                feature_index += 1

    return tensor, times, keys
