import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

EVENT_TYPES = [
    "build", "breakdown", "drop", "fake_drop", "pause_break", "vocal_tail", "energy_reset",
    "drop_explode", "drop_groove", "drop_punch", "soft_release", "anthem_call", "call_response",
    "hook_phrase", "vocal_spotlight", "no_drop_plateau", "tension_hold", "groove_loop",
    "atmospheric_plateau", "percussion_break", "instrumental_bed", "layer_add", "layer_remove",
    "impact_hit", "stinger", "heartbeat_pattern", "four_on_the_floor"
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
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        # x is (Batch, Channels, SeqLen)
        x = self.pool1(self.relu1(self.bn1(self.conv1(x))))
        x = self.pool2(self.relu2(self.bn2(self.conv2(x))))
        x = self.pool3(self.relu3(self.bn3(self.conv3(x))))
        x = x.view(x.size(0), -1)
        return self.fc_head(x)

def parse_contextual_features(filepath: Path) -> tuple[torch.Tensor, dict[int, float], list[str]]:
    if not filepath.exists():
        return torch.empty(0), {}, []
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    records = data.get("features", [])
    if not records:
        return torch.empty(0), {}, []
        
    times = {i: row.get("time_s", 0.0) for i, row in enumerate(records)}
    
    # gather keys from first row safely
    keys = []
    row0 = records[0]
    keys.extend([f"norm_{k}" for k in row0.get("normalized", {})])
    keys.extend([f"deriv_{k}" for k in row0.get("derived", {})])
    for scale, window in row0.get("rolling", {}).items():
        keys.extend([f"roll_{scale}_{k}" for k in window])
            
    num_features = len(keys)
    seq_len = len(records)
    tensor = torch.zeros((num_features, seq_len), dtype=torch.float32)
    
    for i, row in enumerate(records):
        idx = 0
        for k in row.get("normalized", {}):
            tensor[idx, i] = float(row.get("normalized", {}).get(k, 0.0))
            idx += 1
        for k in row.get("derived", {}):
            tensor[idx, i] = float(row.get("derived", {}).get(k, 0.0))
            idx += 1
        for scale, window in row.get("rolling", {}).items():
            for k in window:
                tensor[idx, i] = float(window.get(k, 0.0))
                idx += 1
                
    return tensor, times, keys
import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

EVENT_TYPES = [
    "build", "breakdown", "drop", "fake_drop", "pause_break", "vocal_tail", "energy_reset",
    "drop_explode", "drop_groove", "drop_punch", "soft_release", "anthem_call", "call_response",
    "hook_phrase", "vocal_spotlight", "no_drop_plateau", "tension_hold", "groove_loop",
    "atmospheric_plateau", "percussion_break", "instrumental_bed", "layer_add", "layer_remove",
    "impact_hit", "stinger", "heartbeat_pattern", "four_on_the_floor"
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
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        # x is (Batch, Channels, SeqLen)
        x = self.pool1(self.relu1(self.bn1(self.conv1(x))))
        x = self.pool2(self.relu2(self.bn2(self.conv2(x))))
        x = self.pool3(self.relu3(self.bn3(self.conv3(x))))
        x = x.view(x.size(0), -1)
        return self.fc_head(x)

def parse_contextual_features(filepath: Path) -> tuple[torch.Tensor, dict[int, float], list[str]]:
    if not filepath.exists():
        return torch.empty(0), {}, []
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    records = data.get("features", [])
    if not records:
        return torch.empty(0), {}, []
        
    times = {i: row.get("time_s", 0.0) for i, row in enumerate(records)}
    
    # gather keys from first row safely
    keys = []
    row0 = records[0]
    keys.extend([f"norm_{k}" for k in row0.get("normalized", {})])
    keys.extend([f"deriv_{k}" for k in row0.get("derived", {})])
    for scale, window in row0.get("rolling", {}).items():
        keys.extend([f"roll_{scale}_{k}" for k in window])
            
    num_features = len(keys)
    seq_len = len(records)
    tensor = torch.zeros((num_features, seq_len), dtype=torch.float32)
    
    for i, row in enumerate(records):
        idx = 0
        for k in row.get("normalized", {}):
            tensor[idx, i] = row.get("normalized", {}).get(k, 0.0)
            idx += 1
        for k in row.get("derived", {}):
            tensor[idx, i] = row.get("derived", {}).get(k, 0.0)
            idx += 1
        for scale, window in row.get("rolling", {}).items():
            for k in window:
                tensor[idx, i] = window.get(k, 0.0)
                idx += 1
                
    return tensor, times, keys
