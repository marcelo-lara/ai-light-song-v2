from __future__ import annotations

import argparse
import copy
import json
import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from analyzer.event_contracts import EventContractError, normalize_event_type
from analyzer.event_ml_models import EVENT_TYPE_TO_IDX, EVENT_TYPES, Event1DCNN, NUM_CLASSES, parse_contextual_features


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / "models" / "event_classifier"
DEFAULT_WINDOW_SIZE = 256
DEFAULT_WINDOW_STRIDE = 32
DEFAULT_BATCH_SIZE = 32
DEFAULT_EPOCHS = 20
DEFAULT_LEARNING_RATE = 1e-3
DEFAULT_VALIDATION_RATIO = 0.2
DEFAULT_CLASSIFICATION_THRESHOLD = 0.5
DEFAULT_PROMOTION_PRECISION = 0.70
DEFAULT_RANDOM_SEED = 7

KEYWORD_EVENT_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("fake drop", "fake-drop", "fakeout", "fake out"), "fake_drop"),
    (("drop explode", "explosive drop", "explosive-drop"), "drop_explode"),
    (("drop groove", "groove drop", "groove-drop"), "drop_groove"),
    (("drop punch", "punch drop", "punch-drop"), "drop_punch"),
    (("soft release", "soft drop", "gentle release"), "soft_release"),
    (("build", "build up", "build-up", "buildup", "tension build", "intro tension"), "build"),
    (("breakdown", "break down", "break-down"), "breakdown"),
    (("pause", "silence", "stop time", "stop-time"), "pause_break"),
    (("vocal tail", "ends slowly", "fade out", "fadeout", "vocal breath", "voice tail"), "vocal_tail"),
    (("energy reset", "reset"), "energy_reset"),
    (("female vocal", "male vocal", "vocal intro", "vocal bridge", "vocal solo", "sing phrase", "vocal tension"), "vocal_spotlight"),
    (("hook", "refrain"), "hook_phrase"),
    (("call and response", "call-response", "call response"), "call_response"),
    (("percussion", "drum", "drums", "snare", "snares", "kick", "kicks", "ride"), "percussion_break"),
    (("instrumental", "groove", "loop", "pattern", "phrase", "verse"), "groove_loop"),
    (("ambient", "atmospheric"), "atmospheric_plateau"),
)


@dataclass(frozen=True)
class SongTrainingData:
    song_name: str
    features: torch.Tensor
    frame_times: list[float]
    feature_keys: list[str]
    labels: torch.Tensor
    label_counts: Counter[str]
    unmapped_hints: list[str]


@dataclass(frozen=True)
class WindowSample:
    song_name: str
    start_index: int
    end_index: int
    start_time: float
    end_time: float
    features: torch.Tensor
    labels: torch.Tensor
    has_event: bool


class EventWindowDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, samples: Sequence[WindowSample]) -> None:
        self.samples = list(samples)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[index]
        return sample.features, sample.labels


def _set_random_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _canonical_hint_text(hint: dict[str, Any]) -> str:
    title = str(hint.get("title", "")).strip()
    summary = str(hint.get("summary", "")).strip()
    return f"{title} {summary}".casefold().replace("-", " ")


def infer_event_types_from_hint(hint: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    title = str(hint.get("title", "")).strip()
    text = _canonical_hint_text(hint)

    if title:
        try:
            labels.append(normalize_event_type(title))
        except EventContractError:
            pass

    for keywords, event_type in KEYWORD_EVENT_RULES:
        if any(keyword in text for keyword in keywords) and event_type not in labels:
            labels.append(event_type)

    if "drop" in text and "drop" not in labels and "fake drop" not in text:
        labels.append("drop")

    return labels


def load_human_hints(filepath: Path) -> list[dict[str, Any]]:
    if not filepath.exists():
        return []
    with filepath.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [dict(row) for row in payload.get("human_hints", []) if isinstance(row, dict)]


def discover_labeled_songs(reference_root: Path, artifacts_root: Path) -> list[str]:
    songs: list[str] = []
    for human_hints_path in sorted(reference_root.glob("*/human/human_hints.json")):
        song_name = human_hints_path.parent.parent.name
        features_path = artifacts_root / song_name / "event_inference" / "contextual_features.json"
        if features_path.exists():
            songs.append(song_name)
    return songs


def _build_label_mask(frame_times: Sequence[float], hints: Sequence[dict[str, Any]]) -> tuple[torch.Tensor, Counter[str], list[str]]:
    mask = torch.zeros((NUM_CLASSES, len(frame_times)), dtype=torch.float32)
    label_counts: Counter[str] = Counter()
    unmapped_hints: list[str] = []

    for hint in hints:
        start_time = float(hint.get("start_time", 0.0))
        end_time = max(start_time, float(hint.get("end_time", start_time)))
        event_types = infer_event_types_from_hint(hint)
        if not event_types:
            unmapped_hints.append(str(hint.get("title", "")))
            continue

        active_indices = [index for index, frame_time in enumerate(frame_times) if start_time <= frame_time <= end_time]
        if not active_indices:
            continue

        start_index = active_indices[0]
        end_index = active_indices[-1] + 1
        for event_type in event_types:
            event_index = EVENT_TYPE_TO_IDX[event_type]
            mask[event_index, start_index:end_index] = 1.0
            label_counts[event_type] += end_index - start_index

    return mask, label_counts, unmapped_hints


def load_song_training_data(song_name: str, artifacts_root: Path, reference_root: Path) -> SongTrainingData | None:
    features_path = artifacts_root / song_name / "event_inference" / "contextual_features.json"
    hints_path = reference_root / song_name / "human" / "human_hints.json"
    feature_tensor, time_map, feature_keys = parse_contextual_features(features_path)
    if feature_tensor.numel() == 0 or not hints_path.exists():
        return None

    frame_times = [float(time_map.get(index, round(index * 0.1, 6))) for index in range(feature_tensor.size(1))]
    labels, label_counts, unmapped_hints = _build_label_mask(frame_times, load_human_hints(hints_path))
    return SongTrainingData(
        song_name=song_name,
        features=feature_tensor,
        frame_times=frame_times,
        feature_keys=feature_keys,
        labels=labels,
        label_counts=label_counts,
        unmapped_hints=unmapped_hints,
    )


def split_song_names(song_names: Sequence[str], validation_ratio: float = DEFAULT_VALIDATION_RATIO) -> tuple[list[str], list[str]]:
    ordered = sorted(song_names)
    if len(ordered) < 2:
        raise ValueError("Story 6.2 training requires at least two labeled songs for a song-level validation split.")
    validation_count = max(1, math.ceil(len(ordered) * validation_ratio))
    validation_count = min(validation_count, len(ordered) - 1)
    return ordered[:-validation_count], ordered[-validation_count:]


def build_window_samples(song_data: SongTrainingData, window_size: int = DEFAULT_WINDOW_SIZE, stride: int = DEFAULT_WINDOW_STRIDE) -> list[WindowSample]:
    sequence_length = song_data.features.size(1)
    last_start = max(0, sequence_length - window_size)
    start_indices = list(range(0, last_start + 1, stride)) or [0]
    if start_indices[-1] != last_start:
        start_indices.append(last_start)

    samples: list[WindowSample] = []
    for start_index in start_indices:
        end_index = min(start_index + window_size, sequence_length)
        feature_window = song_data.features[:, start_index:end_index]
        label_window = song_data.labels[:, start_index:end_index]
        if feature_window.size(1) < window_size:
            pad = window_size - feature_window.size(1)
            feature_window = torch.nn.functional.pad(feature_window, (0, pad))
            label_window = torch.nn.functional.pad(label_window, (0, pad))

        window_labels = torch.max(label_window, dim=1).values if label_window.numel() else torch.zeros(NUM_CLASSES)
        samples.append(
            WindowSample(
                song_name=song_data.song_name,
                start_index=start_index,
                end_index=end_index,
                start_time=float(song_data.frame_times[start_index]),
                end_time=float(song_data.frame_times[end_index - 1]),
                features=feature_window.to(dtype=torch.float32),
                labels=window_labels.to(dtype=torch.float32),
                has_event=bool(window_labels.any().item()),
            )
        )
    return samples


def _sampler_for_training(samples: Sequence[WindowSample]) -> WeightedRandomSampler | None:
    positive_count = sum(1 for sample in samples if sample.has_event)
    negative_count = len(samples) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None
    positive_weight = min(8.0, max(1.0, negative_count / positive_count))
    weights = [positive_weight if sample.has_event else 1.0 for sample in samples]
    return WeightedRandomSampler(weights, num_samples=len(samples), replacement=True)


def _metrics_from_logits(logits: torch.Tensor, labels: torch.Tensor, threshold: float) -> dict[str, float]:
    probabilities = torch.sigmoid(logits)
    predictions = probabilities >= threshold
    truth = labels >= 0.5

    true_positive = int((predictions & truth).sum().item())
    false_positive = int((predictions & ~truth).sum().item())
    false_negative = int((~predictions & truth).sum().item())

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "precision": round(float(precision), 6),
        "recall": round(float(recall), 6),
        "f1": round(float(f1), 6),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def _run_epoch(
    model: Event1DCNN,
    dataloader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    threshold: float = DEFAULT_CLASSIFICATION_THRESHOLD,
) -> tuple[float, dict[str, float]]:
    training = optimizer is not None
    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_examples = 0
    logits_batches: list[torch.Tensor] = []
    label_batches: list[torch.Tensor] = []

    for batch_features, batch_labels in dataloader:
        batch_features = batch_features.to(device)
        batch_labels = batch_labels.to(device)

        if training:
            optimizer.zero_grad()

        with torch.set_grad_enabled(training):
            batch_logits = model(batch_features)
            batch_loss = criterion(batch_logits, batch_labels)
            if training:
                batch_loss.backward()
                optimizer.step()

        batch_size = batch_features.size(0)
        total_loss += float(batch_loss.item()) * batch_size
        total_examples += batch_size
        logits_batches.append(batch_logits.detach().cpu())
        label_batches.append(batch_labels.detach().cpu())

    average_loss = total_loss / total_examples if total_examples else 0.0
    if not logits_batches:
        return average_loss, {"precision": 0.0, "recall": 0.0, "f1": 0.0, "true_positive": 0, "false_positive": 0, "false_negative": 0}

    return average_loss, _metrics_from_logits(torch.cat(logits_batches, dim=0), torch.cat(label_batches, dim=0), threshold)


def _resolve_device(device_name: str | None) -> torch.device:
    if device_name:
        return torch.device(device_name)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def train_event_classifier(
    songs_root: Path,
    artifacts_root: Path,
    output_dir: Path = DEFAULT_MODEL_DIR,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    window_size: int = DEFAULT_WINDOW_SIZE,
    stride: int = DEFAULT_WINDOW_STRIDE,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    threshold: float = DEFAULT_CLASSIFICATION_THRESHOLD,
    promotion_precision: float = DEFAULT_PROMOTION_PRECISION,
    device_name: str | None = None,
    random_seed: int = DEFAULT_RANDOM_SEED,
    enforce_promotion_gate: bool = True,
) -> dict[str, Any]:
    if epochs <= 0:
        raise ValueError("epochs must be greater than zero")

    _set_random_seed(random_seed)
    labeled_songs = discover_labeled_songs(songs_root, artifacts_root)
    if len(labeled_songs) < 2:
        raise ValueError("At least two songs with both contextual features and human hints are required.")

    training_song_names, validation_song_names = split_song_names(labeled_songs, validation_ratio)
    song_payloads: dict[str, SongTrainingData] = {}
    for song_name in labeled_songs:
        payload = load_song_training_data(song_name, artifacts_root, songs_root)
        if payload is not None:
            song_payloads[song_name] = payload

    if set(training_song_names) - set(song_payloads) or set(validation_song_names) - set(song_payloads):
        missing = sorted((set(training_song_names) | set(validation_song_names)) - set(song_payloads))
        raise ValueError(f"Missing training inputs for songs: {missing}")

    feature_keys = song_payloads[training_song_names[0]].feature_keys
    for song_name, payload in song_payloads.items():
        if payload.feature_keys != feature_keys:
            raise ValueError(f"Feature schema mismatch for {song_name}; Story 6.2 training requires a consistent contextual feature catalog.")

    training_samples = [sample for song_name in training_song_names for sample in build_window_samples(song_payloads[song_name], window_size, stride)]
    validation_samples = [sample for song_name in validation_song_names for sample in build_window_samples(song_payloads[song_name], window_size, stride)]
    if not training_samples or not validation_samples:
        raise ValueError("Training and validation splits must each contain at least one window.")

    training_dataset = EventWindowDataset(training_samples)
    validation_dataset = EventWindowDataset(validation_samples)
    training_sampler = _sampler_for_training(training_samples)
    training_loader = DataLoader(
        training_dataset,
        batch_size=batch_size,
        shuffle=training_sampler is None,
        sampler=training_sampler,
    )
    validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False)

    device = _resolve_device(device_name)
    model = Event1DCNN(num_features=len(feature_keys)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.BCEWithLogitsLoss()

    train_losses: list[float] = []
    validation_losses: list[float] = []
    best_state: dict[str, torch.Tensor] | None = None
    best_metrics: dict[str, float] | None = None
    best_epoch = 0

    for epoch_index in range(epochs):
        train_loss, _ = _run_epoch(model, training_loader, criterion, device, optimizer, threshold)
        validation_loss, validation_metrics = _run_epoch(model, validation_loader, criterion, device, None, threshold)
        train_losses.append(round(train_loss, 6))
        validation_losses.append(round(validation_loss, 6))

        should_replace_best = best_metrics is None or validation_metrics["f1"] > best_metrics["f1"]
        if not should_replace_best and best_metrics is not None and validation_metrics["f1"] == best_metrics["f1"]:
            should_replace_best = validation_metrics["precision"] > best_metrics["precision"]
        if should_replace_best:
            best_state = copy.deepcopy(model.state_dict())
            best_metrics = dict(validation_metrics)
            best_epoch = epoch_index + 1

    if best_state is None or best_metrics is None:
        raise RuntimeError("Training finished without producing a best checkpoint.")

    output_dir.mkdir(parents=True, exist_ok=True)
    weights_path = output_dir / "1d_cnn_v1.pth"
    metadata_path = output_dir / "metadata.json"

    train_positive_windows = sum(1 for sample in training_samples if sample.has_event)
    validation_positive_windows = sum(1 for sample in validation_samples if sample.has_event)
    cinderella_metrics = None
    if "Cinderella - Ella Lee" in song_payloads:
        cinderella_samples = build_window_samples(song_payloads["Cinderella - Ella Lee"], window_size, stride)
        cinderella_loader = DataLoader(EventWindowDataset(cinderella_samples), batch_size=batch_size, shuffle=False)
        model.load_state_dict(best_state)
        _, cinderella_metrics = _run_epoch(model, cinderella_loader, criterion, device, None, threshold)
        cinderella_metrics["positive_windows"] = sum(1 for sample in cinderella_samples if sample.has_event)

    promotion_ready = bool(epochs >= DEFAULT_EPOCHS and best_metrics["precision"] >= promotion_precision)
    metadata = {
        "schema_version": "1.0",
        "model_name": "event_classifier_1d_cnn_v1",
        "generated_from": {
            "reference_root": str(songs_root),
            "artifacts_root": str(artifacts_root),
        },
        "songs": {
            "all": labeled_songs,
            "train": training_song_names,
            "validation": validation_song_names,
        },
        "dataset": {
            "window_size": window_size,
            "stride": stride,
            "num_features": len(feature_keys),
            "feature_keys": feature_keys,
            "train_windows": len(training_samples),
            "validation_windows": len(validation_samples),
            "train_positive_windows": train_positive_windows,
            "validation_positive_windows": validation_positive_windows,
            "label_frame_counts": dict(sorted(sum((payload.label_counts for payload in song_payloads.values()), Counter()).items())),
            "unmapped_hints": {song_name: payload.unmapped_hints for song_name, payload in song_payloads.items() if payload.unmapped_hints},
        },
        "training": {
            "epochs_requested": epochs,
            "epochs_completed": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "threshold": threshold,
            "device": str(device),
            "best_epoch": best_epoch,
            "train_loss_history": train_losses,
            "validation_loss_history": validation_losses,
            "best_validation_metrics": best_metrics,
            "promotion_threshold_precision": promotion_precision,
            "promotion_ready": promotion_ready,
        },
        "cinderella_check": cinderella_metrics,
        "artifacts": {
            "weights_path": str(weights_path),
            "metadata_path": str(metadata_path),
        },
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    if enforce_promotion_gate and not promotion_ready:
        raise RuntimeError(
            f"Best validation precision {best_metrics['precision']:.3f} did not meet the promotion threshold of {promotion_precision:.3f}."
        )

    torch.save(best_state, weights_path)
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.train_event_classifier",
        description="Train the Story 6.2 1D-CNN event classifier from contextual features and human hints.",
    )
    parser.add_argument("--songs-root", default="/data/reference")
    parser.add_argument("--artifacts-root", default="/data/artifacts")
    parser.add_argument("--output-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE)
    parser.add_argument("--stride", type=int, default=DEFAULT_WINDOW_STRIDE)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO)
    parser.add_argument("--threshold", type=float, default=DEFAULT_CLASSIFICATION_THRESHOLD)
    parser.add_argument("--promotion-threshold", type=float, default=DEFAULT_PROMOTION_PRECISION)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--device")
    parser.add_argument("--allow-below-threshold", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    metadata = train_event_classifier(
        songs_root=Path(args.songs_root),
        artifacts_root=Path(args.artifacts_root),
        output_dir=Path(args.output_dir),
        epochs=args.epochs,
        batch_size=args.batch_size,
        window_size=args.window_size,
        stride=args.stride,
        learning_rate=args.learning_rate,
        validation_ratio=args.validation_ratio,
        threshold=args.threshold,
        promotion_precision=args.promotion_threshold,
        device_name=args.device,
        random_seed=args.seed,
        enforce_promotion_gate=not args.allow_below_threshold,
    )
    best_metrics = metadata["training"]["best_validation_metrics"]
    print(
        "Trained Story 6.2 event classifier "
        f"(precision={best_metrics['precision']:.3f}, recall={best_metrics['recall']:.3f}, f1={best_metrics['f1']:.3f})"
    )
    print(f"Weights: {metadata['artifacts']['weights_path']}")
    print(f"Metadata: {metadata['artifacts']['metadata_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
