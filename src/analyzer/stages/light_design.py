from __future__ import annotations

from collections import defaultdict

from analyzer.io import ensure_directory, read_json
from analyzer.paths import SongPaths


def _split_song_name(song_name: str) -> tuple[str, str | None]:
    if " - " not in song_name:
        return song_name, None
    title, artist = song_name.split(" - ", 1)
    return title.strip(), artist.strip()


def _format_seconds(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}s"


def _classify_fixture_roles(fixtures: list[dict]) -> dict[str, list[str]]:
    roles: dict[str, list[str]] = defaultdict(list)
    for fixture in fixtures:
        fixture_id = str(fixture.get("id") or "")
        fixture_type = str(fixture.get("fixture") or "")
        if "head_el150" in fixture_type:
            role = "moving_head_main"
        elif "moving_head" in fixture_type:
            role = "moving_head_fx"
        elif fixture_id in {"parcan_l", "parcan_r"}:
            role = "parcan_inner"
        elif fixture_id in {"parcan_pl", "parcan_pr"}:
            role = "parcan_outer"
        else:
            role = "support"
        roles[role].append(fixture_id)
    return dict(sorted(roles.items()))


def _role_intention(role: str) -> str:
    mapping = {
        "moving_head_main": "Carries section changes, chorus pushes, and the largest cross-stage gestures.",
        "moving_head_fx": "Answers motif and pattern callbacks with tighter motion, width shifts, and mirrored accents.",
        "parcan_inner": "Provides the central wash, harmonic color identity, and phrase-level brightness support.",
        "parcan_outer": "Frames transitions, release moments, and section contrast with broader edge color.",
        "support": "Fills any remaining role-specific needs without overriding the primary section intent.",
    }
    return mapping.get(role, "Supports the lighting design without overriding the primary section logic.")


def _high_level_brightness(section_energy: list[dict]) -> str:
    if not section_energy:
        return "unknown"
    loudest = max(section_energy, key=lambda row: float(row.get("mean", 0.0)))
    quietest = min(section_energy, key=lambda row: float(row.get("mean", 0.0)))
    return (
        f"Build from {quietest.get('section_name', 'early')} restraint toward "
        f"{loudest.get('section_name', 'peak')} emphasis, then ease into the outro release."
    )


def _feature_summary_lines(
    energy: dict,
    patterns: dict,
    symbolic: dict,
    unified: dict,
) -> list[str]:
    motif_summary = symbolic.get("motif_summary", {})
    repeated_groups = motif_summary.get("repeated_phrase_groups", [])
    dominant_motif_id = motif_summary.get("dominant_motif_id")
    pattern_rows = patterns.get("patterns", [])
    dominant_pattern = pattern_rows[0].get("id") if pattern_rows else None
    section_names = [row.get("section_name") for row in energy.get("section_energy", [])]
    unique_sections = []
    for name in section_names:
        if name and name not in unique_sections:
            unique_sections.append(name)

    summary = [
        f"- Dominant harmonic loop: {dominant_pattern or 'not established'}.",
        f"- Dominant motif group: {dominant_motif_id or 'not established'}.",
        f"- Repeated phrase groups: {len(repeated_groups)}.",
        f"- Global energy arc: {energy.get('global_energy', {}).get('energy_trend', 'unknown')}.",
        f"- Structural path: {', '.join(unique_sections) if unique_sections else 'unknown'}.",
    ]
    description = symbolic.get("description")
    if description:
        summary.append(f"- Symbolic character: {description}")
    cue_anchor_count = len(unified.get("lighting_context", {}).get("cue_anchors", []))
    summary.append(f"- Deterministic cue anchors available: {cue_anchor_count}.")
    return summary


def _timing_anchor_lines(unified: dict, patterns: dict) -> list[str]:
    lines: list[str] = []
    for section in unified.get("timeline", {}).get("sections", []):
        lines.append(
            f"- Section `{section.get('label', section.get('section_id'))}`: "
            f"{_format_seconds(section.get('start'))} -> {_format_seconds(section.get('end'))}"
        )
    for phrase in unified.get("timeline", {}).get("phrases", [])[:12]:
        lines.append(
            f"- Phrase `{phrase.get('id')}`: {_format_seconds(phrase.get('start_s'))} -> {_format_seconds(phrase.get('end_s'))}"
        )
    for accent in unified.get("timeline", {}).get("accent_windows", [])[:12]:
        lines.append(
            f"- Accent `{accent.get('id')}` ({accent.get('kind')}): {_format_seconds(accent.get('time_s'))}"
        )
    for pattern in patterns.get("patterns", [])[:4]:
        for index, occurrence in enumerate(pattern.get("occurrences", [])[:3], start=1):
            lines.append(
                f"- Pattern `{pattern.get('id')}` occurrence {index}: "
                f"{_format_seconds(occurrence.get('start_s'))} -> {_format_seconds(occurrence.get('end_s'))}"
            )
    return lines


def _visual_strategy_lines(energy: dict, lighting_events: dict) -> list[str]:
    global_energy = energy.get("global_energy", {})
    dominant_bass_motion = lighting_events.get("metadata", {}).get("dominant_bass_motion") or "mixed"
    return [
        f"- Palette logic: keep intros and outros cooler, let choruses and repeated callbacks move warmer or brighter.",
        f"- Movement philosophy: tie motion density to transient density and let bass motion `{dominant_bass_motion}` decide pulse character.",
        f"- Contrast strategy: reserve the highest intensity for repeated-section payoffs and strong accent clusters.",
        f"- Boundary treatment: section starts should read as explicit cue changes, not gradual guesswork.",
        f"- Brightness trend: {global_energy.get('energy_trend', 'unknown')} with controlled release at the end.",
    ]


def _fixture_intention_lines(fixtures: list[dict]) -> list[str]:
    roles = _classify_fixture_roles(fixtures)
    lines: list[str] = []
    for role, fixture_ids in roles.items():
        fixture_list = ", ".join(f"`{fixture_id}`" for fixture_id in fixture_ids)
        lines.append(f"- `{role}`: {fixture_list} — {_role_intention(role)}")
    return lines


def _section_plan_lines(unified: dict, lighting_events: dict) -> list[str]:
    sections = unified.get("timeline", {}).get("sections", [])
    phrases = unified.get("timeline", {}).get("phrases", [])
    accents = unified.get("timeline", {}).get("accent_windows", [])
    events = lighting_events.get("lighting_events", [])

    lines: list[str] = []
    for section in sections:
        section_id = section.get("section_id")
        section_label = section.get("label", section_id)
        section_phrases = [row for row in phrases if row.get("section_id") == section_id][:4]
        section_accents = [row for row in accents if row.get("section_id") == section_id][:6]
        section_event = next(
            (row for row in events if row.get("event_type") == "section_scene" and row.get("anchor_refs", {}).get("section_id") == section_id),
            None,
        )

        lines.append(f"### {section_label}")
        lines.append(f"- Window: {_format_seconds(section.get('start'))} -> {_format_seconds(section.get('end'))}")
        if section_phrases:
            phrase_ids = ", ".join(f"`{row.get('id')}`" for row in section_phrases)
            lines.append(f"- Phrase anchors: {phrase_ids}")
        if section_accents:
            accent_times = ", ".join(_format_seconds(row.get("time_s")) for row in section_accents)
            lines.append(f"- Accent anchors: {accent_times}")
        if section_event:
            lines.append(
                f"- Intensity guidance: scene `{section_event.get('scene')}` at {section_event.get('intensity')}, "
                f"movement {section_event.get('movement_speed')}, color family `{section_event.get('color_family')}`."
            )
            lines.append(
                f"- Callback behavior: variation mode `{section_event.get('variation_mode')}`, "
                f"pulse `{section_event.get('pulse_behavior')}`, accent mode `{section_event.get('accent_mode')}`."
            )
        else:
            lines.append("- Intensity guidance: follow the canonical section scene with explicit anchors only.")
        lines.append("")
    return lines


def _song_specific_rule_lines(lighting_events: dict, patterns: dict) -> list[str]:
    event_rows = lighting_events.get("lighting_events", [])
    pattern_rows = patterns.get("patterns", [])
    rise_count = sum(1 for row in event_rows if row.get("scene") == "accent_rise")
    return [
        "- Do not move cue times away from deterministic section, phrase, accent, or pattern anchors.",
        "- Keep intro and outro looks more restrained than the chorus and late-verse pushes.",
        f"- Reuse harmonic callbacks from {len(pattern_rows)} detected pattern groups with controlled variation instead of unrelated new looks.",
        f"- Preserve rise accents as separate moments; current design exposes {rise_count} rise-style accent cues.",
        "- Keep fixture roles stable across the song so repeated motifs feel intentionally recalled rather than randomly reassigned.",
    ]


def _build_lighting_score_markdown(paths: SongPaths) -> str:
    unified = read_json(paths.artifact("music_feature_layers.json"))
    symbolic = read_json(paths.artifact("layer_b_symbolic.json"))
    energy = read_json(paths.artifact("layer_c_energy.json"))
    patterns = read_json(paths.artifact("layer_d_patterns.json"))
    lighting_events = read_json(paths.artifact("lighting_events.json"))
    fixtures = read_json(paths.artifacts_root.parent / "fixtures" / "fixtures.json")

    title, artist = _split_song_name(paths.song_name)
    metadata = unified.get("metadata", {})
    section_energy = energy.get("section_energy", [])

    lines = [
        "# Lighting Score",
        "",
        "## Metadata",
        f"- Song: {title}",
        f"- Artist: {artist or 'Unknown artist'}",
        f"- Duration: {_format_seconds(metadata.get('duration_s'))}",
        f"- BPM: {metadata.get('bpm')}",
        f"- Time Signature: {metadata.get('time_signature')}",
        f"- Key: {metadata.get('key')}",
        f"- High-level energy trend: {energy.get('global_energy', {}).get('energy_trend', 'unknown')}",
        f"- High-level brightness trend: {_high_level_brightness(section_energy)}",
        "",
        "## Feature Summary",
        *_feature_summary_lines(energy, patterns, symbolic, unified),
        "",
        "## Timing Anchors",
        *_timing_anchor_lines(unified, patterns),
        "",
        "## Visual Strategy",
        *_visual_strategy_lines(energy, lighting_events),
        "",
        "## Fixture Intentions",
        *_fixture_intention_lines(fixtures),
        "",
        "## Section Plan",
        *_section_plan_lines(unified, lighting_events),
        "## Song-Specific Rules",
        *_song_specific_rule_lines(lighting_events, patterns),
        "",
    ]
    return "\n".join(lines)


def generate_lighting_score(paths: SongPaths) -> dict:
    markdown = _build_lighting_score_markdown(paths)
    ensure_directory(paths.song_output_dir)
    score_path = paths.song_output_dir / "lighting_score.md"
    score_path.write_text(markdown, encoding="utf-8")
    return {
        "lighting_score_file": str(score_path),
    }