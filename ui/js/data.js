import { encodePath } from "./utils.js";

export async function fetchJson(parts) {
  const response = await fetch(encodePath(parts), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchDirectoryListing(parts) {
  const response = await fetch(encodePath(parts), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const html = await response.text();
  const parser = new DOMParser();
  const documentNode = parser.parseFromString(html, "text/html");
  const links = Array.from(documentNode.querySelectorAll("a"));

  return links
    .map((link) => link.getAttribute("href") || "")
    .filter((href) => href.endsWith("/") && href !== "../")
    .map((href) => decodeURIComponent(href.replace(/\/$/, "")))
    .filter((name) => name && name !== "data" && name !== "artifacts")
    .sort((left, right) => left.localeCompare(right));
}

function normalizeBeatRow(row) {
  const beatInBar = Number(row.beat_in_bar ?? row.beat ?? 0);
  return {
    index: Number(row.index ?? row.beat ?? 0),
    bar: Number(row.bar ?? 0),
    beat_in_bar: beatInBar,
    time: Number(row.time ?? 0),
    type: String(row.type || (beatInBar === 1 ? "downbeat" : "beat")),
  };
}

function buildBarsFromBeats(beats, duration) {
  const bars = [];
  const downbeats = beats.filter((beat) => beat.beat_in_bar === 1);
  for (let index = 0; index < downbeats.length; index += 1) {
    const current = downbeats[index];
    const next = downbeats[index + 1];
    bars.push({
      bar: current.bar,
      start_s: current.time,
      end_s: next ? next.time : duration,
    });
  }
  return bars;
}

function normalizeSection(section, index) {
  return {
    id: String(section.section_id ?? `section-${index + 1}`),
    label: String(section.label ?? section.section_character ?? section.section_name ?? `section_${index + 1}`),
    start_s: Number(section.start ?? section.start_s ?? 0),
    end_s: Number(section.end ?? section.end_s ?? 0),
    confidence: Number(section.confidence ?? 0),
    description: section.description || null,
  };
}

function normalizeChord(chord, index) {
  return {
    id: `chord-${index + 1}`,
    label: String(chord.chord ?? chord.label ?? "?"),
    start_s: Number(chord.time ?? chord.start_time ?? chord.start_s ?? 0),
    end_s: Number(chord.end_s ?? chord.end_time ?? chord.time ?? 0),
    confidence: Number(chord.confidence ?? 0),
  };
}

function normalizePhrase(phrase, index) {
  return {
    id: String(phrase.id ?? phrase.phrase_window_id ?? `phrase-${index + 1}`),
    label: String(phrase.label ?? phrase.phrase_group_id ?? `Phrase ${index + 1}`),
    group_id: String(phrase.phrase_group_id ?? ""),
    start_s: Number(phrase.start_s ?? phrase.start_time ?? 0),
    end_s: Number(phrase.end_s ?? phrase.end_time ?? 0),
  };
}

function flattenPatterns(patternPayload) {
  const patterns = [];
  for (const pattern of patternPayload?.patterns || []) {
    for (const occurrence of pattern.occurrences || []) {
      patterns.push({
        id: `${pattern.id}-${patterns.length + 1}`,
        label: String(pattern.label ?? pattern.id ?? "Pattern"),
        sequence: String(occurrence.sequence ?? pattern.sequence ?? ""),
        start_s: Number(occurrence.start_s ?? 0),
        end_s: Number(occurrence.end_s ?? 0),
        start_bar: Number(occurrence.start_bar ?? 0),
        end_bar: Number(occurrence.end_bar ?? 0),
      });
    }
  }
  return patterns;
}

function buildSeriesRows(rows, beats, duration, mode) {
  return rows.map((row, index) => {
    const beatNumber = Number(row.beat ?? row.index ?? index + 1);
    const beat = beats.find((candidate) => candidate.index === beatNumber) || beats[index];
    const nextBeat = beats.find((candidate) => candidate.index === beatNumber + 1) || beats[index + 1];
    return {
      id: `${mode}-${beatNumber}`,
      beat: beatNumber,
      bar: Number(row.bar ?? beat?.bar ?? 0),
      beat_in_bar: Number(row.beat_in_bar ?? beat?.beat_in_bar ?? 0),
      start_s: Number(row.start_s ?? row.time ?? beat?.time ?? 0),
      end_s: Number(row.end_s ?? nextBeat?.time ?? duration),
      value: mode === "density"
        ? Number(row.density ?? row.normalized?.symbolic_density ?? 0)
        : Number(row.energy_score ?? row.mean ?? row.normalized?.energy_score ?? 0),
    };
  });
}

function buildEventComparisons(machineEvents, timelineEvents) {
  const timelineById = new Map((timelineEvents || []).map((event) => [String(event.id), event]));
  const comparisons = [];

  for (const event of machineEvents || []) {
    const timeline = timelineById.get(String(event.id));
    if (!timeline) {
      comparisons.push({
        id: String(event.id),
        label: String(event.type),
        start_s: Number(event.start_time ?? 0),
        end_s: Number(event.end_time ?? 0),
        status: "not_exported",
      });
      continue;
    }

    const startDelta = Number(timeline.start_time ?? 0) - Number(event.start_time ?? 0);
    const endDelta = Number(timeline.end_time ?? 0) - Number(event.end_time ?? 0);
    comparisons.push({
      id: String(event.id),
      label: String(event.type),
      start_s: Number(timeline.start_time ?? event.start_time ?? 0),
      end_s: Number(timeline.end_time ?? event.end_time ?? 0),
      status: Math.abs(startDelta) < 0.02 && Math.abs(endDelta) < 0.02 ? "exact" : "shifted",
    });
  }

  for (const event of timelineEvents || []) {
    if (!machineEvents?.some((candidate) => String(candidate.id) === String(event.id))) {
      comparisons.push({
        id: String(event.id),
        label: String(event.type),
        start_s: Number(event.start_time ?? 0),
        end_s: Number(event.end_time ?? 0),
        status: "output_only",
      });
    }
  }

  return comparisons.sort((left, right) => left.start_s - right.start_s);
}

export function buildTimelineData(data) {
  const beats = Array.isArray(data.beatsArtifact?.beats)
    ? data.beatsArtifact.beats.map(normalizeBeatRow)
    : Array.isArray(data.eventIndex?.beats)
      ? data.eventIndex.beats.map(normalizeBeatRow)
      : [];
  const duration = Number(
    data.info?.duration
      ?? data.beatsArtifact?.duration
      ?? data.eventFeatures?.metadata?.duration_s
      ?? beats.at(-1)?.time
      ?? 0,
  );

  return {
    beats,
    bars: Array.isArray(data.beatsArtifact?.bars)
      ? data.beatsArtifact.bars.map((bar) => ({
        bar: Number(bar.bar),
        start_s: Number(bar.start_s),
        end_s: Number(bar.end_s),
      }))
      : buildBarsFromBeats(beats, duration),
    duration,
    bpm: Number(data.info?.bpm ?? data.beatsArtifact?.bpm ?? 0),
    sections: Array.isArray(data.sectionsArtifact?.sections)
      ? data.sectionsArtifact.sections.map(normalizeSection)
      : Array.isArray(data.sectionsOutput)
        ? data.sectionsOutput.map(normalizeSection)
        : [],
    chords: Array.isArray(data.harmonic?.chords)
      ? data.harmonic.chords.map(normalizeChord)
      : [],
    phrases: Array.isArray(data.symbolic?.phrase_windows)
      ? data.symbolic.phrase_windows.map(normalizePhrase)
      : Array.isArray(data.eventIndex?.phrases)
        ? data.eventIndex.phrases.map((phrase, index) => normalizePhrase({
          id: phrase.phrase_window_id,
          phrase_group_id: phrase.phrase_group_id,
          start_s: phrase.start_time,
          end_s: phrase.end_time,
        }, index))
        : [],
    patterns: flattenPatterns(data.patterns),
    machineEvents: Array.isArray(data.eventMachine?.events) ? data.eventMachine.events : [],
    timelineEvents: Array.isArray(data.eventsTimeline?.events) ? data.eventsTimeline.events : [],
    drums: Array.isArray(data.drums?.events) ? data.drums.events : [],
    densityRows: Array.isArray(data.symbolic?.density_per_beat)
      ? buildSeriesRows(data.symbolic.density_per_beat, beats, duration, "density")
      : buildSeriesRows(data.eventFeatures?.features || [], beats, duration, "density"),
    energyRows: Array.isArray(data.energy?.beat_energy)
      ? buildSeriesRows(data.energy.beat_energy, beats, duration, "energy")
      : buildSeriesRows(data.eventFeatures?.features || [], beats, duration, "energy"),
    accentCandidates: Array.isArray(data.energy?.accent_candidates)
      ? data.energy.accent_candidates
      : Array.isArray(data.eventIndex?.accents)
        ? data.eventIndex.accents
        : [],
    validationDrift: Array.isArray(data.validation?.validation?.beats?.details)
      ? data.validation.validation.beats.details
      : [],
    eventComparisons: buildEventComparisons(
      Array.isArray(data.eventMachine?.events) ? data.eventMachine.events : [],
      Array.isArray(data.eventsTimeline?.events) ? data.eventsTimeline.events : [],
    ),
  };
}