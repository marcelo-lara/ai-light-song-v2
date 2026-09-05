// Pure parsers: one per artifact the UI reads. Each takes the raw parsed JSON
// and returns a typed value, throwing `ShapeError` on a contract mismatch.
// The loaders (loaders.ts) wrap these; the tests exercise them directly against
// fixtures taken from real `data/analysis/_test_song/` artifacts.

import {
  ShapeError,
  asArray,
  asNumber,
  asObject,
  asString,
  numberArray,
  numberOr,
  numberOrNull,
  objectOrNull,
  stringOr,
  stringOrNull,
} from "./parse";
import type {
  Beats,
  BeatRow,
  DrumEvent,
  DrumEventsFile,
  EnergyAccent,
  EnergyBeat,
  EnergyLayer,
  EventTimeline,
  FftBands,
  FftBand,
  FftFrame,
  HarmonicChord,
  HarmonicLayer,
  HumanHint,
  HumanHintsFile,
  LoudnessFrame,
  LoudnessHistory,
  LoudnessSeries,
  LoudnessSource,
  ReviewQuestion,
  ReviewQueue,
  SectionRow,
  SectionSegmentation,
  SectionsTopLevel,
  SegmentationSection,
  SongFact,
  SongFactsFile,
  SongInfo,
  TimelineEvent,
} from "./types";

function stringRecord(value: unknown, ctx: string): Record<string, string> {
  const obj = asObject(value, ctx);
  const out: Record<string, string> = {};
  for (const [key, entry] of Object.entries(obj)) {
    // Real info.json files carry `null` for artifacts that were not produced
    // (e.g. `human_hints_alignment`). Skip those rather than failing the whole
    // document — an absent path is simply an absent entry.
    if (entry === null || entry === undefined) continue;
    out[key] = asString(entry, `${ctx}.${key}`);
  }
  return out;
}

// ---------------------------------------------------------------------------

export function parseInfo(raw: unknown): SongInfo {
  const o = asObject(raw, "info.json");
  return {
    schema_version: stringOr(o.schema_version, "", "info.schema_version"),
    song_name: asString(o.song_name, "info.song_name"),
    bpm: numberOr(o.bpm, 0, "info.bpm"),
    duration: asNumber(o.duration, "info.duration"),
    song_path: stringOr(o.song_path, "", "info.song_path"),
    artifacts: stringRecord(o.artifacts ?? {}, "info.artifacts"),
    outputs:
      o.outputs === undefined || o.outputs === null
        ? null
        : stringRecord(o.outputs, "info.outputs"),
    generated_from: objectOrNull(o.generated_from, "info.generated_from"),
    debug: objectOrNull(o.debug, "info.debug"),
  };
}

// ---------------------------------------------------------------------------

function parseBeatRow(raw: unknown, ctx: string): BeatRow {
  const o = asObject(raw, ctx);
  return {
    time: asNumber(o.time, `${ctx}.time`),
    beat: asNumber(o.beat, `${ctx}.beat`),
    bar: asNumber(o.bar, `${ctx}.bar`),
    bass: stringOrNull(o.bass, `${ctx}.bass`),
    chord: stringOrNull(o.chord, `${ctx}.chord`),
    type: stringOr(o.type, "beat", `${ctx}.type`),
    confidence: numberOrNull(o.confidence, `${ctx}.confidence`),
  };
}

export function parseBeats(raw: unknown): Beats {
  return asArray(raw, "beats.json").map((row, i) =>
    parseBeatRow(row, `beats[${i}]`),
  );
}

// ---------------------------------------------------------------------------

function parseSectionRow(raw: unknown, ctx: string): SectionRow {
  const o = asObject(raw, ctx);
  return {
    section_id: asString(o.section_id, `${ctx}.section_id`),
    start: asNumber(o.start, `${ctx}.start`),
    end: asNumber(o.end, `${ctx}.end`),
    label: asString(o.label, `${ctx}.label`),
    description: stringOrNull(o.description, `${ctx}.description`),
    confidence: numberOrNull(o.confidence, `${ctx}.confidence`),
  };
}

export function parseSectionsTopLevel(raw: unknown): SectionsTopLevel {
  return asArray(raw, "sections.json").map((row, i) =>
    parseSectionRow(row, `sections[${i}]`),
  );
}

// ---------------------------------------------------------------------------

function parseSegmentationSection(
  raw: unknown,
  ctx: string,
): SegmentationSection {
  const o = asObject(raw, ctx);
  return {
    section_id: asString(o.section_id, `${ctx}.section_id`),
    start: asNumber(o.start, `${ctx}.start`),
    end: asNumber(o.end, `${ctx}.end`),
    function: stringOrNull(o.function, `${ctx}.function`),
    function_confidence: numberOrNull(
      o.function_confidence,
      `${ctx}.function_confidence`,
    ),
    function_status: stringOrNull(
      o.function_status,
      `${ctx}.function_status`,
    ),
    same_label_as: stringOrNull(o.same_label_as, `${ctx}.same_label_as`),
    confidence: numberOrNull(o.confidence, `${ctx}.confidence`),
  };
}

export function parseSectionSegmentation(raw: unknown): SectionSegmentation {
  const o = asObject(raw, "section_segmentation/sections.json");
  const sections = asArray(o.sections, "segmentation.sections").map((s, i) =>
    parseSegmentationSection(s, `segmentation.sections[${i}]`),
  );

  // v1.1 B5 — the join key is `section_id`; a missing/duplicate id would
  // silently misalign every section downstream. Fail loudly, as build_ui_data
  // itself does.
  const seen = new Set<string>();
  for (const section of sections) {
    if (seen.has(section.section_id)) {
      throw new ShapeError(
        `segmentation.sections: duplicate section_id "${section.section_id}"`,
      );
    }
    seen.add(section.section_id);
  }

  return {
    schema_version: stringOr(o.schema_version, "", "segmentation.schema_version"),
    song_name: stringOr(o.song_name, "", "segmentation.song_name"),
    generated_from: objectOrNull(
      o.generated_from,
      "segmentation.generated_from",
    ),
    sections,
  };
}

// ---------------------------------------------------------------------------

function parseFftBand(raw: unknown, ctx: string): FftBand {
  const o = asObject(raw, ctx);
  return {
    id: asString(o.id, `${ctx}.id`),
    label: asString(o.label, `${ctx}.label`),
    start_hz: asNumber(o.start_hz, `${ctx}.start_hz`),
    end_hz: asNumber(o.end_hz, `${ctx}.end_hz`),
  };
}

function parseFftFrame(raw: unknown, ctx: string): FftFrame {
  const o = asObject(raw, ctx);
  return {
    frame_index: asNumber(o.frame_index, `${ctx}.frame_index`),
    time: asNumber(o.time, `${ctx}.time`),
    levels: numberArray(o.levels, `${ctx}.levels`),
    brightness_ratio: numberOrNull(
      o.brightness_ratio,
      `${ctx}.brightness_ratio`,
    ),
    transient_strength: numberOrNull(
      o.transient_strength,
      `${ctx}.transient_strength`,
    ),
    dropout_strength: numberOrNull(
      o.dropout_strength,
      `${ctx}.dropout_strength`,
    ),
  };
}

export function parseFftBands(raw: unknown): FftBands {
  const o = asObject(raw, "fft_bands.json");
  return {
    schema_version: stringOr(o.schema_version, "", "fft.schema_version"),
    song_name: stringOr(o.song_name, "", "fft.song_name"),
    bands: asArray(o.bands, "fft.bands").map((b, i) =>
      parseFftBand(b, `fft.bands[${i}]`),
    ),
    frames: asArray(o.frames, "fft.frames").map((f, i) =>
      parseFftFrame(f, `fft.frames[${i}]`),
    ),
    metadata: objectOrNull(o.metadata, "fft.metadata"),
  };
}

// ---------------------------------------------------------------------------

function parseLoudnessSource(raw: unknown, ctx: string): LoudnessSource {
  const o = asObject(raw, ctx);
  return {
    id: asString(o.id, `${ctx}.id`),
    label: asString(o.label, `${ctx}.label`),
    path: stringOr(o.path, "", `${ctx}.path`),
    kind: stringOr(o.kind, "stem", `${ctx}.kind`),
  };
}

function parseLoudnessHistory(
  raw: unknown,
  ctx: string,
): LoudnessHistory | null {
  if (raw === undefined || raw === null) return null;
  const o = asObject(raw, ctx);
  return {
    mean_2s: numberArray(o.mean_2s ?? [], `${ctx}.mean_2s`),
    peak_2s: numberArray(o.peak_2s ?? [], `${ctx}.peak_2s`),
    mean_5s: numberArray(o.mean_5s ?? [], `${ctx}.mean_5s`),
    peak_5s: numberArray(o.peak_5s ?? [], `${ctx}.peak_5s`),
  };
}

function parseLoudnessFrame(raw: unknown, ctx: string): LoudnessFrame {
  const o = asObject(raw, ctx);
  return {
    frame_index: asNumber(o.frame_index, `${ctx}.frame_index`),
    time: asNumber(o.time, `${ctx}.time`),
    start_s: numberOrNull(o.start_s, `${ctx}.start_s`),
    end_s: numberOrNull(o.end_s, `${ctx}.end_s`),
    values: numberArray(o.values, `${ctx}.values`),
    normalized_values: numberArray(
      o.normalized_values ?? [],
      `${ctx}.normalized_values`,
    ),
    history: parseLoudnessHistory(o.history, `${ctx}.history`),
  };
}

export function parseLoudnessSeries(
  raw: unknown,
  file = "loudness series",
): LoudnessSeries {
  const o = asObject(raw, file);
  return {
    schema_version: stringOr(o.schema_version, "", `${file}.schema_version`),
    song_name: stringOr(o.song_name, "", `${file}.song_name`),
    sources: asArray(o.sources, `${file}.sources`).map((s, i) =>
      parseLoudnessSource(s, `${file}.sources[${i}]`),
    ),
    frames: asArray(o.frames, `${file}.frames`).map((f, i) =>
      parseLoudnessFrame(f, `${file}.frames[${i}]`),
    ),
    metadata: objectOrNull(o.metadata, `${file}.metadata`),
  };
}

export const parseRmsLoudness = (raw: unknown): LoudnessSeries =>
  parseLoudnessSeries(raw, "rms_loudness.json");
export const parseLoudnessEnvelope = (raw: unknown): LoudnessSeries =>
  parseLoudnessSeries(raw, "loudness_envelope.json");

// ---------------------------------------------------------------------------

function parseHarmonicChord(raw: unknown, ctx: string): HarmonicChord {
  const o = asObject(raw, ctx);
  return {
    time: asNumber(o.time, `${ctx}.time`),
    end_s: asNumber(o.end_s, `${ctx}.end_s`),
    bar: numberOrNull(o.bar, `${ctx}.bar`),
    beat: numberOrNull(o.beat, `${ctx}.beat`),
    chord: asString(o.chord, `${ctx}.chord`),
    confidence: numberOrNull(o.confidence, `${ctx}.confidence`),
  };
}

export function parseHarmonicLayer(raw: unknown): HarmonicLayer {
  const o = asObject(raw, "layer_a_harmonic.json");
  const gk = objectOrNull(o.global_key, "harmonic.global_key");
  return {
    schema_version: stringOr(o.schema_version, "", "harmonic.schema_version"),
    song_name: stringOr(o.song_name, "", "harmonic.song_name"),
    global_key: gk
      ? {
          label: stringOrNull(gk.label, "harmonic.global_key.label"),
          confidence: numberOrNull(
            gk.confidence,
            "harmonic.global_key.confidence",
          ),
          source: stringOrNull(gk.source, "harmonic.global_key.source"),
        }
      : null,
    chords: asArray(o.chords, "harmonic.chords").map((c, i) =>
      parseHarmonicChord(c, `harmonic.chords[${i}]`),
    ),
    chord_probabilities: o.chord_probabilities ?? null,
  };
}

// ---------------------------------------------------------------------------

export function parseHumanHint(raw: unknown, ctx = "human_hint"): HumanHint {
  const o = asObject(raw, ctx);
  return {
    id: asString(o.id, `${ctx}.id`),
    title: stringOr(
      (o.title ?? o.label) as unknown,
      "",
      `${ctx}.title`,
    ),
    start_time: numberOr(
      (o.start_time ?? o.start_s ?? o.start) as unknown,
      0,
      `${ctx}.start_time`,
    ),
    end_time: numberOr(
      (o.end_time ?? o.end_s ?? o.end) as unknown,
      0,
      `${ctx}.end_time`,
    ),
    summary: stringOr(o.summary, "", `${ctx}.summary`),
    lighting_hint: stringOr(o.lighting_hint, "", `${ctx}.lighting_hint`),
  };
}

export function parseHumanHints(raw: unknown): HumanHintsFile {
  const o = asObject(raw, "human_hints.json");
  const list = asArray(o.human_hints ?? [], "human_hints.human_hints");
  return {
    song_name: stringOr(o.song_name, "", "human_hints.song_name"),
    human_hints: list.map((h, i) =>
      parseHumanHint(h, `human_hints.human_hints[${i}]`),
    ),
  };
}

// ---------------------------------------------------------------------------

function parseDrumEvent(raw: unknown, ctx: string, index: number): DrumEvent {
  const o = asObject(raw, ctx);
  const time = numberOr(o.time, 0, `${ctx}.time`);
  return {
    id: stringOr(
      (o.event_id ?? o.id) as unknown,
      `drum-${String(index + 1).padStart(5, "0")}`,
      `${ctx}.id`,
    ),
    time,
    end_s: Math.max(numberOr(o.end_s, time, `${ctx}.end_s`), time),
    event_type: stringOr(o.event_type, "unresolved", `${ctx}.event_type`),
  };
}

export function parseDrumEvents(raw: unknown): DrumEventsFile {
  const o = asObject(raw, "drum_events.json");
  const events = asArray(o.events ?? [], "drum_events.events")
    .map((e, i) => parseDrumEvent(e, `drum_events.events[${i}]`, i))
    .sort((a, b) => a.time - b.time);
  return {
    schema_version: stringOr(o.schema_version, "", "drum_events.schema_version"),
    song_name: stringOr(o.song_name, "", "drum_events.song_name"),
    events,
  };
}

// ---------------------------------------------------------------------------

function parseEnergyBeat(raw: unknown, ctx: string): EnergyBeat {
  const o = asObject(raw, ctx);
  return {
    time: numberOr(o.time, 0, `${ctx}.time`),
    energy_score: numberOr(o.energy_score, 0, `${ctx}.energy_score`),
    bar: numberOrNull(o.bar, `${ctx}.bar`),
    beat: numberOrNull(o.beat_in_bar ?? o.beat, `${ctx}.beat`),
  };
}

function parseEnergyAccent(raw: unknown, ctx: string, index: number): EnergyAccent {
  const o = asObject(raw, ctx);
  return {
    id: stringOr(
      (o.id ?? o.accent_id) as unknown,
      `accent-${String(index + 1).padStart(3, "0")}`,
      `${ctx}.id`,
    ),
    time: numberOr(o.time, 0, `${ctx}.time`),
    intensity: numberOr(o.intensity, 0, `${ctx}.intensity`),
    kind: stringOr(o.kind, "hit", `${ctx}.kind`),
  };
}

export function parseEnergyLayer(raw: unknown): EnergyLayer {
  const o = asObject(raw, "layer_c_energy.json");
  return {
    schema_version: stringOr(o.schema_version, "", "energy.schema_version"),
    song_name: stringOr(o.song_name, "", "energy.song_name"),
    beat_energy: asArray(o.beat_energy ?? [], "energy.beat_energy")
      .map((b, i) => parseEnergyBeat(b, `energy.beat_energy[${i}]`))
      .sort((a, b) => a.time - b.time),
    accent_candidates: asArray(o.accent_candidates ?? [], "energy.accent_candidates")
      .map((a, i) => parseEnergyAccent(a, `energy.accent_candidates[${i}]`, i))
      .sort((a, b) => a.time - b.time),
  };
}

// ---------------------------------------------------------------------------

function parseTimelineEvent(raw: unknown, ctx: string): TimelineEvent {
  const o = asObject(raw, ctx);
  return {
    type: asString(o.type, `${ctx}.type`),
    start_time: asNumber(o.start_time, `${ctx}.start_time`),
    end_time: asNumber(o.end_time, `${ctx}.end_time`),
    confidence: numberOr(o.confidence, 0, `${ctx}.confidence`),
    intensity: numberOr(o.intensity, 0, `${ctx}.intensity`),
    section_id: stringOrNull(o.section_id, `${ctx}.section_id`),
    section_name: stringOrNull(o.section_name, `${ctx}.section_name`),
    provenance: stringOrNull(o.provenance, `${ctx}.provenance`),
    summary: stringOrNull(o.summary, `${ctx}.summary`),
    evidence_summary: stringOrNull(
      o.evidence_summary,
      `${ctx}.evidence_summary`,
    ),
  };
}

export function parseEventTimeline(raw: unknown): EventTimeline {
  const o = asObject(raw, "song_event_timeline.json");
  return {
    schema_version: stringOr(o.schema_version, "", "timeline.schema_version"),
    song_name: stringOr(o.song_name, "", "timeline.song_name"),
    generated_from: objectOrNull(o.generated_from, "timeline.generated_from"),
    events: asArray(o.events, "timeline.events").map((e, i) =>
      parseTimelineEvent(e, `timeline.events[${i}]`),
    ),
  };
}

// ---------------------------------------------------------------------------

function parseReviewQuestion(raw: unknown, ctx: string): ReviewQuestion {
  const o = asObject(raw, ctx);
  return {
    field: asString(o.field, `${ctx}.field`),
    candidates: asArray(o.candidates ?? [], `${ctx}.candidates`).map((c, i) => {
      const co = asObject(c, `${ctx}.candidates[${i}]`);
      return {
        value: co.value ?? null,
        score: numberOr(co.score, 0, `${ctx}.candidates[${i}].score`),
      };
    }),
    evidence_timestamps: numberArray(
      o.evidence_timestamps ?? [],
      `${ctx}.evidence_timestamps`,
    ),
    reason_low_confidence: stringOrNull(
      o.reason_low_confidence,
      `${ctx}.reason_low_confidence`,
    ),
    leverage: numberOrNull(o.leverage, `${ctx}.leverage`),
  };
}

export function parseSongFacts(raw: unknown): SongFactsFile {
  const o = asObject(raw, "song_facts.json");
  const factsRaw = objectOrNull(o.facts, "song_facts.facts") ?? {};
  const facts: Record<string, SongFact> = {};
  for (const [key, entry] of Object.entries(factsRaw)) {
    const fo = asObject(entry, `song_facts.facts.${key}`);
    facts[key] = {
      value: fo.value ?? null,
      provenance: stringOrNull(fo.provenance, `song_facts.facts.${key}.provenance`),
      confirmed_on: stringOrNull(
        fo.confirmed_on,
        `song_facts.facts.${key}.confirmed_on`,
      ),
      note: stringOrNull(fo.note, `song_facts.facts.${key}.note`),
    };
  }
  return {
    schema_version: stringOr(o.schema_version, "", "song_facts.schema_version"),
    song_name: stringOr(o.song_name, "", "song_facts.song_name"),
    facts,
  };
}

export function parseReviewQueue(raw: unknown): ReviewQueue {
  const o = asObject(raw, "review_queue.json");
  return {
    schema_version: stringOr(o.schema_version, "", "review_queue.schema_version"),
    song_name: stringOr(o.song_name, "", "review_queue.song_name"),
    direction_of_flow: stringOrNull(
      o.direction_of_flow,
      "review_queue.direction_of_flow",
    ),
    open_question_count: numberOrNull(
      o.open_question_count,
      "review_queue.open_question_count",
    ),
    questions: asArray(o.questions ?? [], "review_queue.questions").map((q, i) =>
      parseReviewQuestion(q, `review_queue.questions[${i}]`),
    ),
  };
}
