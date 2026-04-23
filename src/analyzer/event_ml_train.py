import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from analyzer.event_ml_models import Event1DCNN, parse_contextual_features, EVENT_TYPE_TO_IDX, NUM_CLASSES
logger = logging.getLogger(__name__)

class EventDataset(Dataset):
    def __init__(self, tensors, labels):
        self.tensors = tensors
        self.labels = labels

    def __len__(self):
        return len(self.tensors)

    def __getitem__(self, idx):
        return self.tensors[idx], self.labels[idx]

def load_human_hints(filepath: Path) -> list:
    if not filepath.exists():
        return []
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get("human_hints", [])

def build_dataset(song_name: str, window_size: int = 256, step_size: int = 128) -> EventDataset:
    features_path = Path(f"/data/artifacts/{song_name}/event_inference/contextual_features.json")
    hints_path = Path(f"/data/reference/{song_name}/human/human_hints.json")

    tensor, times, _ = parse_contextual_features(features_path)
    if tensor.numel() == 0:
        return EventDataset([], [])

    hints = load_human_hints(hints_path)
    
    seq_len = tensor.size(1)
    
    # generate labels at 100ms grid
    grid_labels = torch.zeros((NUM_CLASSES, seq_len), dtype=torch.float32)
    for hint in hints:
        start_t = hint.get("start_time", 0.0)
        end_t = hint.get("end_time", 0.0)
        
        raw_title = hint.get("title", "").lower().replace(" candidate", "")
        # map title to canonical
        try:
            canon = "breakdown" # default
            # mapping logic: we see "Breakdown Candidate" in hints
            if "breakdown" in raw_title:
                canon = "breakdown"
            elif "drop" in raw_title:
                canon = "drop"
            event_idx = EVENT_TYPE_TO_IDX.get(canon, None)
            if event_idx is None:
                continue
            
            for i in range(seq_len):
                if start_t <= times.get(i, 0.0) <= end_t:
                    grid_labels[event_idx, i] = 1.0
        except Exception:
            pass

    # windowing
    tensors = []
    labels = []
    
    for i in range(0, seq_len - window_size + 1, step_size):
        window_feature = tensor[:, i:i+window_size] # (Features, Window)
        window_label = grid_labels[:, i:i+window_size] # (Classes, Window)
        
        # label for window = 1 if max across time is 1
        window_label = torch.max(window_label, dim=1).values
        
        tensors.append(window_feature)
        labels.append(window_label)
        
    return EventDataset(tensors, labels)

def train_model():
    song_name = "Cinderella - Ella Lee"
    dataset = build_dataset(song_name)
    if len(dataset) == 0:
        print("Failed to build dataset (missing files or empty features).")
        return
    
    dataloader = DataLoader(dataset, batch_size=8, shuffle=True)
    model = Event1DCNN(num_features=44)
    
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    epochs = 10
    print(f"Training on {len(dataset)} windows for {epochs} epochs...")
    model.train()
    
    for epoch in range(epochs):
        epoch_loss = 0.0
        for X, Y in dataloader:
            optimizer.zero_grad()
            out = model(X) # (B, Classes)
            loss = criterion(out, Y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            
        print(f"Epoch {epoch+1}/{epochs}, Loss: {epoch_loss/len(dataloader):.4f}")
        
    out_dir = Path("/data/artifacts/models/event_classifier")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "1d_cnn_v1.pth"
    torch.save(model.state_dict(), out_path)
    print(f"Saved model to {out_path}")

if __name__ == "__main__":
    train_model()
