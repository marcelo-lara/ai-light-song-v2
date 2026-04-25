from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import urllib.request
from typing import TYPE_CHECKING

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION, to_jsonable

if TYPE_CHECKING:
    from analyzer.paths import SongPaths


UNKNOWN_GENRE = "unknown"
CO_WINNER_MARGIN_RATIO = 0.5
GENRE_SAMPLE_RATE = 16000
GENRE_CHUNK_SECONDS = 30.0
GENRE_CHUNK_HOP_SECONDS = 15.0

# Model provenance metadata
GENRE_MODEL_NAME = "essentia-tensorflow-genre"
GENRE_MODEL_VERSION = "1.0"

# Dedicated repository model path
ESSENTIA_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "essentia"
ESSENTIA_GENRE_MODEL_FILE = "msd-musicnn.pb"
ESSENTIA_GENRE_METADATA_FILE = "msd-musicnn.json"


@dataclass(slots=True)
class GenrePrediction:
    """Single genre prediction with confidence."""

    label: str
    confidence: float


@dataclass(slots=True)
class GenreResult:
    """Complete genre classification result."""

    genres: list[str]
    confidence: float
    top_predictions: list[GenrePrediction]


def _load_audio_for_genre(song_path: str) -> "np.ndarray":
    """Load audio using Essentia's MonoLoader."""
    try:
        from essentia.standard import MonoLoader
    except ImportError as exc:
        raise DependencyError("essentia is required for genre classification") from exc

    # Essentia genre models typically use 16kHz
    audio = MonoLoader(filename=song_path, sampleRate=GENRE_SAMPLE_RATE)()
    return audio


def _iter_genre_chunks(audio: "np.ndarray") -> list["np.ndarray"]:
    total_samples = int(audio.shape[0])
    if total_samples <= 0:
        return []

    chunk_samples = max(1, int(GENRE_CHUNK_SECONDS * GENRE_SAMPLE_RATE))
    hop_samples = max(1, int(GENRE_CHUNK_HOP_SECONDS * GENRE_SAMPLE_RATE))

    if total_samples <= chunk_samples:
        return [audio]

    chunks: list[np.ndarray] = []
    start = 0
    while start < total_samples:
        end = min(total_samples, start + chunk_samples)
        chunk = audio[start:end]
        if chunk.size > 0:
            chunks.append(chunk)
        if end >= total_samples:
            break
        start += hop_samples
    return chunks


def _ensure_genre_model() -> None:
    """Download the Essentia genre model and metadata if missing."""
    ESSENTIA_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Download model .pb
    model_path = ESSENTIA_MODEL_DIR / ESSENTIA_GENRE_MODEL_FILE
    if not model_path.exists():
        url = "https://essentia.upf.edu/models/autotagging/msd/msd-musicnn-1.pb"
        print(f"[GENRE] Downloading model weights from {url}")
        try:
            urllib.request.urlretrieve(url, str(model_path))
        except Exception as exc:
            raise DependencyError(f"Failed to download genre model: {exc}") from exc

    # Download model .json
    meta_path = ESSENTIA_MODEL_DIR / ESSENTIA_GENRE_METADATA_FILE
    if not meta_path.exists():
        url = "https://essentia.upf.edu/models/autotagging/msd/msd-musicnn-1.json"
        print(f"[GENRE] Downloading model metadata from {url}")
        try:
            urllib.request.urlretrieve(url, str(meta_path))
        except Exception as exc:
            raise DependencyError(f"Failed to download genre metadata: {exc}") from exc


def _load_genre_model_label_names() -> list[str]:
    """Load the model-native Essentia label set from metadata."""
    import json

    metadata_path = ESSENTIA_MODEL_DIR / ESSENTIA_GENRE_METADATA_FILE
    if not metadata_path.exists():
        raise AnalysisError(
            f"Genre model metadata not available. Expected file at {metadata_path}"
        )

    with open(metadata_path, encoding="utf-8") as handle:
        metadata = json.load(handle)

    label_names = metadata.get("classes", [])
    if not label_names:
        raise AnalysisError(
            f"Genre model metadata at {metadata_path} does not define any classes"
        )

    return label_names


def _run_essentia_genre_classifier(
    audio: "np.ndarray",
) -> tuple[dict[str, float], list[str]]:
    """Run Essentia TensorFlow genre classifier on audio.

    Returns model-native label confidences plus the ordered model label list.
    """
    try:
        from essentia.standard import TensorflowPredictMusiCNN
    except ImportError as exc:
        raise DependencyError("essentia with TensorFlow support is required for genre classification") from exc

    # Use the musiCNN-based auto-tagging model and keep the model-native labels.
    try:
        # Attempt to load the genre model
        # Note: This requires the model files to be available
        # The model files are typically downloaded separately
        
        # Use MusicCNN model which is the most reliable available option
        model_path = ESSENTIA_MODEL_DIR / ESSENTIA_GENRE_MODEL_FILE
        label_names = _load_genre_model_label_names()

        if not model_path.exists():
            raise AnalysisError(
                f"Genre model not available. Expected model file at {model_path}"
            )

        genre_predictor = TensorflowPredictMusiCNN(
            graphFilename=str(model_path),
            savedModel="",
            input="model/Placeholder",
            output="model/Sigmoid",
            isTrainingName="model/Placeholder_1",
        )

        # Process the song in chunks to reduce peak TensorFlow GPU memory.
        prediction_rows: list[np.ndarray] = []
        for chunk in _iter_genre_chunks(audio):
            chunk_predictions = genre_predictor(chunk)
            chunk_rows = np.asarray(chunk_predictions, dtype=float)
            if chunk_rows.ndim == 1:
                chunk_rows = chunk_rows.reshape(1, -1)
            if chunk_rows.size > 0:
                prediction_rows.append(chunk_rows)

        if not prediction_rows:
            raise AnalysisError("Genre model returned no prediction rows")

        predictions = np.concatenate(prediction_rows, axis=0)
        mean_scores = np.mean(predictions, axis=0)

        # Build confidence mapping
        confidences = {}
        for label, confidence in zip(label_names, mean_scores):
            confidences[label] = float(confidence)
            
        return confidences, [*label_names, UNKNOWN_GENRE]
        
    except Exception as exc:
        raise AnalysisError(f"Genre model inference failed: {exc}") from exc


def _normalize_predictions(
    raw_predictions: dict[str, float],
    allowed_labels: list[str],
) -> GenreResult:
    """Select model-native winning labels from raw Essentia predictions.

    - Keeps the Essentia label names unchanged
    - Selects the top label when it stands above the average confidence
    - Includes co-winners that stay close to the top score
    - Returns sorted top predictions
    """
    if not raw_predictions:
        return GenreResult(
            genres=[UNKNOWN_GENRE],
            confidence=0.0,
            top_predictions=[],
        )

    # Sort by confidence descending
    sorted_predictions = sorted(
        raw_predictions.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    # Build GenrePrediction list with all valid predictions
    top_predictions = [
        GenrePrediction(label=label, confidence=round(confidence, 6))
        for label, confidence in sorted_predictions
        if label != UNKNOWN_GENRE
    ]

    # Get top prediction
    top_label, top_confidence = sorted_predictions[0]
    average_confidence = sum(raw_predictions.values()) / len(raw_predictions)
    confidence_margin = top_confidence - average_confidence

    # Treat a flat score distribution as ambiguous rather than forcing a label.
    if confidence_margin <= 0.0:
        return GenreResult(
            genres=[UNKNOWN_GENRE],
            confidence=round(top_confidence, 6),
            top_predictions=top_predictions,
        )

    # Ensure top prediction is one of the model-defined labels.
    if top_label not in allowed_labels[:-1]:
        return GenreResult(
            genres=[UNKNOWN_GENRE],
            confidence=round(top_confidence, 6),
            top_predictions=top_predictions,
        )

    co_winner_margin = confidence_margin * CO_WINNER_MARGIN_RATIO
    selected_genres = [
        label
        for label, confidence in sorted_predictions
        if label in allowed_labels[:-1] and (top_confidence - confidence) <= co_winner_margin
    ]

    if not selected_genres:
        selected_genres = [top_label]

    return GenreResult(
        genres=selected_genres,
        confidence=round(top_confidence, 6),
        top_predictions=top_predictions,
    )


def classify_genre(paths: SongPaths) -> dict:
    """Classify the genre of a song.

    Uses an approved third-party model (Essentia TensorFlow music auto-tagger).
    Returns `["unknown"]` if the model is unavailable, fails, or produces
    an ambiguous score distribution with no top label above the model average.

    Args:
        paths: SongPaths containing song and artifact locations

    Returns:
        Dictionary with genre classification result matching the story schema
    """
    # Load audio
    audio = _load_audio_for_genre(str(paths.song_path))

    # Run genre classification
    try:
        _ensure_genre_model()
        raw_predictions, allowed_labels = _run_essentia_genre_classifier(audio)
        result = _normalize_predictions(raw_predictions, allowed_labels)
    except (AnalysisError, DependencyError) as exc:
        # Model unavailable or failed - return unknown as per story requirements
        # Do NOT implement custom fallback from handcrafted heuristics
        print(f"[GENRE] Model failed: {exc}")
        print("[GENRE] Falling back to 'unknown' genre (no handcrafted heuristic fallback used)")
        try:
            allowed_labels = [*_load_genre_model_label_names(), UNKNOWN_GENRE]
        except AnalysisError:
            allowed_labels = [UNKNOWN_GENRE]
        result = GenreResult(
            genres=[UNKNOWN_GENRE],
            confidence=0.0,
            top_predictions=[],
        )

    # Build output payload matching story schema
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": GENRE_MODEL_NAME,
            "dependencies": {
                "model_name": GENRE_MODEL_NAME,
                "model_version": GENRE_MODEL_VERSION,
            },
        },
        "genres": result.genres,
        "confidence": result.confidence,
        "top_predictions": [
            {"label": pred.label, "confidence": pred.confidence}
            for pred in result.top_predictions[:5]  # Limit to top 5
        ],
        "guidance": [
            "Use the genre only as review guidance for what song parts are likely to matter.",
            "Do not assume genre-specific drops or section semantics unless downstream evidence supports them.",
        ],
    }

    # Write artifact
    artifact_path = paths.artifact("genre.json")
    write_json(artifact_path, to_jsonable(payload))

    return payload
