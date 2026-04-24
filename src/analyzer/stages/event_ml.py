from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch

from analyzer.event_ml_models import EVENT_TYPES, Event1DCNN, parse_contextual_features
from analyzer.io import read_json, write_json
from analyzer.paths import SongPaths


MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "event_classifier"
MODEL_PATH = MODEL_DIR / "1d_cnn_v1.pth"
PENALTY_METADATA_PATH = MODEL_DIR / "penalty_logic_metadata.json"

WINDOW_SIZE = 256
STEP_SIZE = 128
EVENT_THRESHOLD = 0.8
SEED = 42


def _find_index(feature_keys: list[str], *candidates: str) -> int | None:
    for candidate in candidates:
        if candidate in feature_keys:
            return feature_keys.index(candidate)
    return None


def _window_average_support(
    chunk: torch.Tensor,
    feature_keys: list[str],
) -> dict[str, float]:
    bass_att_idx = _find_index(feature_keys, "deriv_bass_att")
    bass_lma_idx = _find_index(feature_keys, "deriv_bass_att_lma")
    flux_idx = _find_index(feature_keys, "norm_spectral_flux")
    flux_lma_idx = _find_index(feature_keys, "deriv_spectral_flux_lma")

    def _mean_channel(index: int | None) -> float:
        if index is None:
            return 0.0
        return float(chunk[index].mean().item())

    bass_att = max(0.0, _mean_channel(bass_att_idx))
    bass_lma = max(1e-6, _mean_channel(bass_lma_idx)) if bass_lma_idx is not None else max(1e-6, bass_att)
    flux = max(0.0, _mean_channel(flux_idx))
    flux_lma = max(1e-6, _mean_channel(flux_lma_idx)) if flux_lma_idx is not None else max(1e-6, flux)

    bass_ratio = bass_att / bass_lma
    flux_ratio = flux / flux_lma
    support_ratio = (bass_ratio + flux_ratio) / 2.0

    return {
        "bass_att": bass_att,
        "bass_att_lma": bass_lma,
        "spectral_flux": flux,
        "spectral_flux_lma": flux_lma,
        "bass_ratio": bass_ratio,
        "flux_ratio": flux_ratio,
        "support_ratio": support_ratio,
    }


def _apply_penalty_and_reward(
    event_type: str,
    confidence: float,
    support: dict[str, float],
    alignment_score: float,
) -> tuple[float, float, float]:
    penalty_classes = {"impact_hit", "breakdown", "drop", "energy_reset"}

    penalty = 0.0
    reward = 0.0
    adjusted_confidence = confidence

    if event_type in penalty_classes and support["support_ratio"] < 1.0:
        penalty = min(0.5, (1.0 - support["support_ratio"]) * 0.5)
        adjusted_confidence = max(0.0, adjusted_confidence * (1.0 - penalty))

    if alignment_score > 0.0:
        reward = min(0.2, alignment_score * 0.2)
        adjusted_confidence = min(1.0, adjusted_confidence + reward)

    return adjusted_confidence, penalty, reward


def _best_alignment_score(
    identifiers: list[dict[str, Any]],
    start_t: float,
    end_t: float,
) -> float:
    best = 0.0
    for event in identifiers:
        start = float(event.get("start_s", event.get("time_s", 0.0)))
        end = float(event.get("end_s", start))
        overlap = max(0.0, min(end_t, end) - max(start_t, start))
        if overlap <= 0.0:
            continue
        score = float(event.get("audit", {}).get("alignment_score", 0.0))
        if score > best:
            best = score
    return best


def _merge_overlapping_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []

    events = sorted(events, key=lambda row: (str(row["type"]), float(row["start_time"]), float(row["end_time"])))
    merged: list[dict[str, Any]] = [dict(events[0])]

    for event in events[1:]:
        previous = merged[-1]
        same_type = str(previous["type"]) == str(event["type"])
        overlaps = float(event["start_time"]) <= float(previous["end_time"]) + 0.25
        if same_type and overlaps:
            previous["end_time"] = max(float(previous["end_time"]), float(event["end_time"]))
            previous["confidence"] = max(float(previous["confidence"]), float(event["confidence"]))
            previous["intensity"] = max(float(previous["intensity"]), float(event["intensity"]))
            prev_windows = previous.setdefault("evidence", {}).setdefault("source_windows", [])
            prev_windows.extend(event.get("evidence", {}).get("source_windows", []))
            continue
        merged.append(dict(event))

    for index, event in enumerate(merged, start=1):
        event["id"] = f"ml_{event['type']}_{index:03d}"
    return merged


def _load_contextual_rows(paths: SongPaths) -> list[dict[str, Any]]:
    contextual_path = paths.artifact("event_inference", "contextual_features.json")
    if not contextual_path.exists():
        return []
    payload = read_json(contextual_path)
    return [dict(row) for row in payload.get("features", [])]


def generate_ml_events(paths: SongPaths) -> dict:
    features_path = paths.artifact("event_inference", "contextual_features.json")
    out_path = paths.artifact("event_inference", "events.ml.json")
    saliency_path = paths.artifact("event_inference", "saliency_explanations.json")
    penalty_timeline_path = paths.artifact("event_inference", "penalty_timeline.json")

    contextual_rows = _load_contextual_rows(paths)
    tensor, times, feature_keys = parse_contextual_features(features_path)

    identifiers_path = paths.artifact("energy_summary", "hints.json")
    identifiers = []
    if identifiers_path.exists():
        identifiers = [dict(row) for row in read_json(identifiers_path).get("events", [])]

    if tensor.numel() == 0:
        empty_payload = {"schema_version": "1.0", "song_name": paths.song_name, "events": []}
        write_json(out_path, empty_payload)
        write_json(saliency_path, {"schema_version": "1.0", "song_name": paths.song_name, "saliency": []})
        write_json(
            penalty_timeline_path,
            {
                "schema_version": "1.0",
                "song_name": paths.song_name,
                "frames": [],
            },
        )
        return empty_payload

    torch.manual_seed(SEED)
    num_features = tensor.shape[0]
    model = Event1DCNN(num_features=num_features)

    if not MODEL_PATH.exists():
        empty_payload = {"schema_version": "1.0", "song_name": paths.song_name, "events": []}
        write_json(out_path, empty_payload)
        write_json(saliency_path, {"schema_version": "1.0", "song_name": paths.song_name, "saliency": []})
        write_json(
            penalty_timeline_path,
            {
                "schema_version": "1.0",
                "song_name": paths.song_name,
                "frames": [],
                "notes": "Model weights were not found; no ML events generated.",
            },
        )
        write_json(
            PENALTY_METADATA_PATH,
            {
                "schema_version": "1.0",
                "model_path": str(MODEL_PATH),
                "seed": SEED,
                "status": "skipped_missing_weights",
            },
        )
        return empty_payload

    model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    model.eval()

    sequence_length = tensor.size(1)
    events: list[dict[str, Any]] = []
    saliency_rows: list[dict[str, Any]] = []
    penalty_rows: list[dict[str, Any]] = []

    with torch.no_grad():
        for start_index in range(0, max(1, sequence_length - WINDOW_SIZE + 1), STEP_SIZE):
            chunk = tensor[:, start_index : start_index + WINDOW_SIZE]
            if chunk.size(1) < WINDOW_SIZE:
                padding = WINDOW_SIZE - chunk.size(1)
                chunk = torch.nn.functional.pad(chunk, (0, padding))

            logits = model(chunk.unsqueeze(0)).squeeze(0)
            probabilities = torch.sigmoid(logits)

            start_t = float(times.get(start_index, round(start_index * 0.1, 6)))
            end_t = float(times.get(min(start_index + WINDOW_SIZE - 1, sequence_length - 1), start_t))

            support = _window_average_support(chunk, feature_keys)
            alignment_score = _best_alignment_score(identifiers, start_t, end_t)

            penalty_rows.append(
                {
                    "start_time": round(start_t, 6),
                    "end_time": round(end_t, 6),
                    "support_ratio": round(support["support_ratio"], 6),
                    "bass_ratio": round(support["bass_ratio"], 6),
                    "flux_ratio": round(support["flux_ratio"], 6),
                    "alignment_score": round(alignment_score, 6),
                }
            )

            feature_importance = torch.mean(torch.abs(chunk), dim=1)
            top_indices = torch.topk(feature_importance, k=min(3, feature_importance.numel())).indices.tolist()
            top_features = [feature_keys[index] for index in top_indices]

            for class_index, probability in enumerate(probabilities.tolist()):
                if probability < EVENT_THRESHOLD:
                    continue

                base_confidence = max(0.0, min(1.0, float(probability)))
                event_type = EVENT_TYPES[class_index]
                adjusted_confidence, penalty, reward = _apply_penalty_and_reward(
                    event_type,
                    base_confidence,
                    support,
                    alignment_score,
                )

                event_id = f"ml_{start_index}_{class_index}"
                events.append(
                    {
                        "id": event_id,
                        "type": event_type,
                        "start_time": round(start_t, 6),
                        "end_time": round(end_t, 6),
                        "confidence": round(adjusted_confidence, 6),
                        "intensity": round(adjusted_confidence, 6),
                        "created_by": "analyzer_ml_classifier_1d_cnn_v1",
                        "evidence": {
                            "summary": "Window-level ML prediction with physical-constraint penalty audit.",
                            "source_windows": [
                                {
                                    "layer": "event_features",
                                    "start_time": round(start_t, 6),
                                    "end_time": round(end_t, 6),
                                    "ref": f"grid:{start_index}-{min(start_index + WINDOW_SIZE - 1, sequence_length - 1)}",
                                    "metric_names": ["support_ratio", "alignment_score"],
                                }
                            ],
                            "metrics": [
                                {"name": "base_probability", "value": round(base_confidence, 6)},
                                {"name": "support_ratio", "value": round(support["support_ratio"], 6)},
                                {"name": "alignment_score", "value": round(alignment_score, 6)},
                                {"name": "penalty", "value": round(penalty, 6)},
                                {"name": "reward", "value": round(reward, 6)},
                            ],
                            "rule_names": ["ml_window_threshold", "physical_constraint_penalty"],
                        },
                        "notes": "Confidence adjusted by physical transient support and identifier alignment evidence.",
                        "source_layers": ["event_features", "energy_identifiers"],
                        "metadata": {
                            "base_confidence": round(base_confidence, 6),
                            "penalty": round(penalty, 6),
                            "reward": round(reward, 6),
                        },
                    }
                )
                saliency_rows.append(
                    {
                        "event_id": event_id,
                        "type": event_type,
                        "time_window": [round(start_t, 6), round(end_t, 6)],
                        "top_features": top_features,
                    }
                )

    merged_events = _merge_overlapping_events(events)

    payload = {
        "schema_version": "1.0",
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "contextual_features_file": str(features_path),
            "model_path": str(MODEL_PATH),
            "seed": SEED,
            "window_size": WINDOW_SIZE,
            "step_size": STEP_SIZE,
        },
        "events": merged_events,
    }

    write_json(out_path, payload)
    write_json(
        saliency_path,
        {
            "schema_version": "1.0",
            "song_name": paths.song_name,
            "generated_from": {"events_file": str(out_path)},
            "saliency": saliency_rows,
        },
    )
    write_json(
        penalty_timeline_path,
        {
            "schema_version": "1.0",
            "song_name": paths.song_name,
            "generated_from": {
                "events_file": str(out_path),
                "contextual_features_file": str(features_path),
            },
            "frames": penalty_rows,
        },
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    write_json(
        PENALTY_METADATA_PATH,
        {
            "schema_version": "1.0",
            "model_path": str(MODEL_PATH),
            "seed": SEED,
            "window_size": WINDOW_SIZE,
            "step_size": STEP_SIZE,
            "event_threshold": EVENT_THRESHOLD,
            "generated_song": paths.song_name,
            "penalty_timeline_file": str(penalty_timeline_path),
        },
    )

    return payload
