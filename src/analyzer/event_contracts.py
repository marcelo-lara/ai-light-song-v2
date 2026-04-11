from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from analyzer.exceptions import AnalysisError


class EventContractError(AnalysisError):
    """Raised when an Epic 5 event payload violates the contract."""


def _contracts_dir() -> Path:
    return Path(__file__).with_name("contracts")


def _load_contract(name: str) -> dict[str, Any]:
    path = _contracts_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_event_vocabulary() -> dict[str, Any]:
    return _load_contract("event_vocabulary.json")


@lru_cache(maxsize=1)
def load_song_event_schema() -> dict[str, Any]:
    return _load_contract("song_event_schema.json")


def _canonicalize_label(value: str) -> str:
    return "_".join(value.strip().casefold().replace("-", " ").split())


@lru_cache(maxsize=1)
def _event_alias_index() -> dict[str, str]:
    alias_index: dict[str, str] = {}
    for event_row in load_event_vocabulary().get("events", []):
        canonical_name = str(event_row["name"])
        labels = [canonical_name, *event_row.get("aliases", [])]
        for label in labels:
            normalized = _canonicalize_label(str(label))
            existing = alias_index.get(normalized)
            if existing is not None and existing != canonical_name:
                raise EventContractError(
                    f"Event vocabulary alias collision for '{label}': {existing} vs {canonical_name}"
                )
            alias_index[normalized] = canonical_name
    return alias_index


@lru_cache(maxsize=1)
def canonical_event_types() -> tuple[str, ...]:
    return tuple(str(event_row["name"]) for event_row in load_event_vocabulary().get("events", []))


def normalize_event_type(event_type: str) -> str:
    normalized = _canonicalize_label(event_type)
    canonical = _event_alias_index().get(normalized)
    if canonical is None:
        raise EventContractError(f"Unknown event type: {event_type}")
    return canonical


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EventContractError(f"{field_name} must be an object")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise EventContractError(f"{field_name} must be a list")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise EventContractError(f"{field_name} must be a string")
    return value


def _require_numeric(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise EventContractError(f"{field_name} must be numeric")
    if not isinstance(value, (int, float)):
        raise EventContractError(f"{field_name} must be numeric")
    return float(value)


def _check_allowed_keys(payload: Mapping[str, Any], allowed_keys: set[str], field_name: str) -> None:
    unknown_keys = sorted(set(payload) - allowed_keys)
    if unknown_keys:
        raise EventContractError(f"{field_name} contains unknown fields: {unknown_keys}")


def _check_required_keys(payload: Mapping[str, Any], required_keys: list[str], field_name: str) -> None:
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise EventContractError(f"{field_name} is missing required fields: {missing}")


def _validate_source_windows(source_windows: Any, allowed_layers: set[str]) -> list[dict[str, Any]]:
    schema = load_song_event_schema()["source_window"]
    rows = _require_list(source_windows, "evidence.source_windows")
    normalized_rows: list[dict[str, Any]] = []
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    for index, row in enumerate(rows):
        mapping = _require_mapping(row, f"evidence.source_windows[{index}]")
        _check_required_keys(mapping, schema["required"], f"evidence.source_windows[{index}]")
        _check_allowed_keys(mapping, allowed_keys, f"evidence.source_windows[{index}]")

        layer = _require_string(mapping["layer"], f"evidence.source_windows[{index}].layer")
        if layer not in allowed_layers:
            raise EventContractError(
                f"evidence.source_windows[{index}].layer must be one of {sorted(allowed_layers)}"
            )

        start_time = _require_numeric(mapping["start_time"], f"evidence.source_windows[{index}].start_time")
        end_time = _require_numeric(mapping["end_time"], f"evidence.source_windows[{index}].end_time")
        if end_time < start_time:
            raise EventContractError(f"evidence.source_windows[{index}] has end_time before start_time")

        normalized_row = {
            "layer": layer,
            "start_time": start_time,
            "end_time": end_time,
        }
        if "ref" in mapping:
            normalized_row["ref"] = _require_string(mapping["ref"], f"evidence.source_windows[{index}].ref")
        if "metric_names" in mapping:
            metric_names = _require_list(mapping["metric_names"], f"evidence.source_windows[{index}].metric_names")
            normalized_row["metric_names"] = [
                _require_string(item, f"evidence.source_windows[{index}].metric_names[{metric_index}]")
                for metric_index, item in enumerate(metric_names)
            ]
        if "notes" in mapping:
            normalized_row["notes"] = _require_string(mapping["notes"], f"evidence.source_windows[{index}].notes")
        normalized_rows.append(normalized_row)
    return normalized_rows


def _validate_metrics(metrics: Any, allowed_layers: set[str]) -> list[dict[str, Any]]:
    schema = load_song_event_schema()["metric"]
    rows = _require_list(metrics, "evidence.metrics")
    normalized_rows: list[dict[str, Any]] = []
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    for index, row in enumerate(rows):
        mapping = _require_mapping(row, f"evidence.metrics[{index}]")
        _check_required_keys(mapping, schema["required"], f"evidence.metrics[{index}]")
        _check_allowed_keys(mapping, allowed_keys, f"evidence.metrics[{index}]")

        normalized_row = {
            "name": _require_string(mapping["name"], f"evidence.metrics[{index}].name"),
            "value": _require_numeric(mapping["value"], f"evidence.metrics[{index}].value"),
        }
        if "unit" in mapping:
            normalized_row["unit"] = _require_string(mapping["unit"], f"evidence.metrics[{index}].unit")
        if "threshold" in mapping:
            normalized_row["threshold"] = _require_numeric(mapping["threshold"], f"evidence.metrics[{index}].threshold")
        if "comparator" in mapping:
            normalized_row["comparator"] = _require_string(mapping["comparator"], f"evidence.metrics[{index}].comparator")
        if "source_layer" in mapping:
            source_layer = _require_string(mapping["source_layer"], f"evidence.metrics[{index}].source_layer")
            if source_layer not in allowed_layers:
                raise EventContractError(
                    f"evidence.metrics[{index}].source_layer must be one of {sorted(allowed_layers)}"
                )
            normalized_row["source_layer"] = source_layer
        if "notes" in mapping:
            normalized_row["notes"] = _require_string(mapping["notes"], f"evidence.metrics[{index}].notes")
        normalized_rows.append(normalized_row)
    return normalized_rows


def _validate_model(model: Any) -> dict[str, Any]:
    schema = load_song_event_schema()["model"]
    mapping = _require_mapping(model, "evidence.model")
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    _check_required_keys(mapping, schema["required"], "evidence.model")
    _check_allowed_keys(mapping, allowed_keys, "evidence.model")

    normalized = {"name": _require_string(mapping["name"], "evidence.model.name")}
    if "version" in mapping:
        normalized["version"] = _require_string(mapping["version"], "evidence.model.version")
    if "confidence_delta" in mapping:
        normalized["confidence_delta"] = _require_numeric(mapping["confidence_delta"], "evidence.model.confidence_delta")
    if "notes" in mapping:
        normalized["notes"] = _require_string(mapping["notes"], "evidence.model.notes")
    return normalized


def validate_evidence(evidence: Any) -> dict[str, Any]:
    schema = load_song_event_schema()
    evidence_schema = schema["evidence"]
    event_schema = schema["event"]
    allowed_layers = set(event_schema["source_layers_enum"])
    mapping = _require_mapping(evidence, "evidence")
    allowed_keys = set(evidence_schema["allowed"])
    _check_allowed_keys(mapping, allowed_keys, "evidence")

    if not any(key in mapping and mapping[key] not in (None, [], "") for key in evidence_schema["required_at_least_one_of"]):
        raise EventContractError(
            "evidence must include at least one populated field from "
            f"{evidence_schema['required_at_least_one_of']}"
        )

    normalized: dict[str, Any] = {}
    if "summary" in mapping:
        normalized["summary"] = _require_string(mapping["summary"], "evidence.summary")
    if "source_windows" in mapping:
        normalized["source_windows"] = _validate_source_windows(mapping["source_windows"], allowed_layers)
    if "metrics" in mapping:
        normalized["metrics"] = _validate_metrics(mapping["metrics"], allowed_layers)
    if "reasons" in mapping:
        reasons = _require_list(mapping["reasons"], "evidence.reasons")
        normalized["reasons"] = [
            _require_string(reason, f"evidence.reasons[{index}]")
            for index, reason in enumerate(reasons)
        ]
    if "rule_names" in mapping:
        rule_names = _require_list(mapping["rule_names"], "evidence.rule_names")
        normalized["rule_names"] = [
            _require_string(name, f"evidence.rule_names[{index}]")
            for index, name in enumerate(rule_names)
        ]
    if "model" in mapping:
        normalized["model"] = _validate_model(mapping["model"])
    if "metadata" in mapping:
        normalized["metadata"] = dict(_require_mapping(mapping["metadata"], "evidence.metadata"))
    return normalized


def _validate_human_override(human_override: Any) -> dict[str, Any]:
    schema = load_song_event_schema()["human_override"]
    mapping = _require_mapping(human_override, "human_override")
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    _check_required_keys(mapping, schema["required"], "human_override")
    _check_allowed_keys(mapping, allowed_keys, "human_override")

    status = _require_string(mapping["status"], "human_override.status")
    if status not in schema["status_enum"]:
        raise EventContractError(
            f"human_override.status must be one of {schema['status_enum']}"
        )

    normalized = {"status": status}
    string_fields = ("editor", "reason", "updated_type", "notes")
    for field_name in string_fields:
        if field_name in mapping:
            value = _require_string(mapping[field_name], f"human_override.{field_name}")
            if field_name == "updated_type":
                value = normalize_event_type(value)
            normalized[field_name] = value
    for field_name in ("updated_start_time", "updated_end_time"):
        if field_name in mapping:
            normalized[field_name] = _require_numeric(mapping[field_name], f"human_override.{field_name}")
    if (
        "updated_start_time" in normalized
        and "updated_end_time" in normalized
        and normalized["updated_end_time"] < normalized["updated_start_time"]
    ):
        raise EventContractError("human_override.updated_end_time cannot be earlier than updated_start_time")
    return normalized


def _validate_lighting_hints(lighting_hints: Any) -> dict[str, Any]:
    schema = load_song_event_schema()["lighting_hints"]
    mapping = _require_mapping(lighting_hints, "lighting_hints")
    _check_allowed_keys(mapping, set(schema["allowed"]), "lighting_hints")

    normalized: dict[str, Any] = {}
    for field_name in ("cue_style", "energy_profile", "notes"):
        if field_name in mapping:
            normalized[field_name] = _require_string(mapping[field_name], f"lighting_hints.{field_name}")
    if "editable" in mapping:
        if not isinstance(mapping["editable"], bool):
            raise EventContractError("lighting_hints.editable must be a boolean")
        normalized["editable"] = mapping["editable"]
    return normalized


def _validate_candidates(candidates: Any) -> list[dict[str, Any]]:
    schema = load_song_event_schema()["candidate"]
    rows = _require_list(candidates, "candidates")
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        mapping = _require_mapping(row, f"candidates[{index}]")
        _check_required_keys(mapping, schema["required"], f"candidates[{index}]")
        _check_allowed_keys(mapping, allowed_keys, f"candidates[{index}]")

        normalized = {
            "type": normalize_event_type(_require_string(mapping["type"], f"candidates[{index}].type")),
            "confidence": _require_numeric(mapping["confidence"], f"candidates[{index}].confidence"),
        }
        if not 0.0 <= normalized["confidence"] <= 1.0:
            raise EventContractError(f"candidates[{index}].confidence must be between 0.0 and 1.0")
        if "notes" in mapping:
            normalized["notes"] = _require_string(mapping["notes"], f"candidates[{index}].notes")
        normalized_rows.append(normalized)
    return normalized_rows


def validate_event_payload(event: Any, *, normalize_aliases: bool = True) -> dict[str, Any]:
    schema = load_song_event_schema()["event"]
    mapping = _require_mapping(event, "event")
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    _check_required_keys(mapping, schema["required"], "event")
    _check_allowed_keys(mapping, allowed_keys, "event")

    normalized_event_type = _require_string(mapping["type"], "event.type")
    if normalize_aliases:
        normalized_event_type = normalize_event_type(normalized_event_type)
    elif normalized_event_type not in canonical_event_types():
        raise EventContractError(f"event.type must be one of {list(canonical_event_types())}")

    start_time = _require_numeric(mapping["start_time"], "event.start_time")
    end_time = _require_numeric(mapping["end_time"], "event.end_time")
    if end_time < start_time:
        raise EventContractError("event.end_time cannot be earlier than event.start_time")

    confidence = _require_numeric(mapping["confidence"], "event.confidence")
    intensity = _require_numeric(mapping["intensity"], "event.intensity")
    for field_name, value in (("confidence", confidence), ("intensity", intensity)):
        numeric_range = schema["numeric_ranges"][field_name]
        if not numeric_range["minimum"] <= value <= numeric_range["maximum"]:
            raise EventContractError(
                f"event.{field_name} must be between {numeric_range['minimum']} and {numeric_range['maximum']}"
            )

    allowed_layers = set(schema["source_layers_enum"])
    normalized = {
        "id": _require_string(mapping["id"], "event.id"),
        "type": normalized_event_type,
        "start_time": start_time,
        "end_time": end_time,
        "confidence": confidence,
        "intensity": intensity,
        "evidence": validate_evidence(mapping["evidence"]),
        "notes": _require_string(mapping["notes"], "event.notes"),
    }

    if "section_name" in mapping:
        normalized["section_name"] = _require_string(mapping["section_name"], "event.section_name")
    if "section_id" in mapping:
        normalized["section_id"] = _require_string(mapping["section_id"], "event.section_id")
    if "source_layers" in mapping:
        source_layers = _require_list(mapping["source_layers"], "event.source_layers")
        normalized_layers = []
        for index, layer in enumerate(source_layers):
            layer_name = _require_string(layer, f"event.source_layers[{index}]")
            if layer_name not in allowed_layers:
                raise EventContractError(
                    f"event.source_layers[{index}] must be one of {sorted(allowed_layers)}"
                )
            normalized_layers.append(layer_name)
        normalized["source_layers"] = normalized_layers
    if "human_override" in mapping:
        normalized["human_override"] = _validate_human_override(mapping["human_override"])
    if "lighting_hints" in mapping:
        normalized["lighting_hints"] = _validate_lighting_hints(mapping["lighting_hints"])
    if "candidates" in mapping:
        normalized["candidates"] = _validate_candidates(mapping["candidates"])
    if "metadata" in mapping:
        normalized["metadata"] = dict(_require_mapping(mapping["metadata"], "event.metadata"))
    return normalized


def validate_song_event_payload(payload: Any, *, normalize_aliases: bool = True) -> dict[str, Any]:
    schema = load_song_event_schema()["top_level"]
    mapping = _require_mapping(payload, "payload")
    allowed_keys = set(schema["required"]) | set(schema["optional"])
    _check_required_keys(mapping, schema["required"], "payload")
    _check_allowed_keys(mapping, allowed_keys, "payload")

    schema_version = _require_string(mapping["schema_version"], "payload.schema_version")
    if schema_version != load_song_event_schema()["schema_version"]:
        raise EventContractError(
            f"payload.schema_version must equal {load_song_event_schema()['schema_version']}"
        )

    normalized = {
        "schema_version": schema_version,
        "song_name": _require_string(mapping["song_name"], "payload.song_name"),
        "generated_from": dict(_require_mapping(mapping["generated_from"], "payload.generated_from")),
        "events": [
            validate_event_payload(event, normalize_aliases=normalize_aliases)
            for event in _require_list(mapping["events"], "payload.events")
        ],
    }
    for field_name in ("review_status", "threshold_profile", "notes"):
        if field_name in mapping:
            normalized[field_name] = _require_string(mapping[field_name], f"payload.{field_name}")
    if "metadata" in mapping:
        normalized["metadata"] = dict(_require_mapping(mapping["metadata"], "payload.metadata"))
    return normalized