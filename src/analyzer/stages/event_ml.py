from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.event_ml_models import parse_contextual_features, Event1DCNN, EVENT_TYPES
import torch
from analyzer.io import write_json


MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "event_classifier" / "1d_cnn_v1.pth"

def generate_ml_events(paths: SongPaths) -> dict:
    features_path = paths.artifact("event_inference", "contextual_features.json")
    out_path = paths.artifact("event_inference", "events.ml.json")
    
    tensor, times, keys = parse_contextual_features(features_path)
    if tensor.numel() == 0:
        return {"schema_version": 1, "events": []}
    
    num_features = tensor.shape[0]
    model = Event1DCNN(num_features=num_features)
    
    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    except Exception as e:
        print(f"Skipping ML events: {e}")
        return {"schema_version": 1, "events": []}

    model.eval()
    
    # Use sliding window of size 256 for inference
    window_sz = 256
    step_sz = 128
    
    seq_len = tensor.size(1)
    
    events = []
    
    with torch.no_grad():
        for i in range(0, max(1, seq_len - window_sz + 1), step_sz):
            chunk = tensor[:, i:i+window_sz]
            if chunk.size(1) < window_sz:
                pad = window_sz - chunk.size(1)
                chunk = torch.nn.functional.pad(chunk, (0, pad))
            
            chunk = chunk.unsqueeze(0)
            logits = model(chunk)
            probs = torch.sigmoid(logits).squeeze(0)
            
            start_t = times.get(i, 0.0)
            end_t = times.get(min(i + window_sz - 1, seq_len - 1), 0.0)
            
            for c_idx, prob in enumerate(probs):
                if prob > 0.8:
                    val = min(1.0, max(0.0, float(prob)))
                    events.append({
                        "id": f"ml_{i}_{c_idx}",
                        "type": EVENT_TYPES[c_idx],
                        "start_time": float(start_t),
                        "end_time": float(end_t),
                        "confidence": val,
                        "intensity": val,
                        "evidence": {
                            "created_by": "analyzer_ml_classifier_1d_cnn_v1",
                            "source_windows": [f"{start_t:.1f}-{end_t:.1f}"]
                        }
                    })
    
    payload = {
        "schema_version": 1,
        "events": events
    }
    
    write_json(out_path, payload)
    return payload
