function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function asNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function asString(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function startOf(row) {
  return asNumber(row?.start_s ?? row?.start_time ?? row?.start ?? row?.time, 0);
}

function endOf(row, startValue) {
  return asNumber(row?.end_s ?? row?.end_time ?? row?.end ?? row?.time, startValue);
}

function sortByStart(left, right) {
  return startOf(left) - startOf(right);
}

function normalizeBeats(beatsArtifact, beatsOutput) {
  const artifactRows = asArray(beatsArtifact?.beats);
  if (artifactRows.length) {
    return artifactRows
      .map((row, index) => ({
        index: asNumber(row.index, index + 1),
        time: asNumber(row.time, 0),
        bar: asNumber(row.bar, 1),
        beat_in_bar: asNumber(row.beat_in_bar ?? row.beat, 1),
        type: asString(row.type, "beat"),
      }))
      .sort((left, right) => left.time - right.time);
  }

  return asArray(beatsOutput)
    .map((row, index) => ({
      index: index + 1,
      time: asNumber(row.time, 0),
      bar: asNumber(row.bar, 1),
      beat_in_bar: asNumber(row.beat_in_bar ?? row.beat, 1),
      type: asString(row.type, asNumber(row.beat_in_bar ?? row.beat, 1) === 1 ? "downbeat" : "beat"),
    }))
    .sort((left, right) => left.time - right.time);
}

function buildBars(beats, barsFromArtifact, duration) {
  const artifactBars = asArray(barsFromArtifact);
  if (artifactBars.length) {
    return artifactBars
      .map((bar, index) => {
        const start = asNumber(bar.start_s ?? bar.start_time ?? bar.start, 0);
        const end = asNumber(bar.end_s ?? bar.end_time ?? bar.end, start);
        return {
          bar: asNumber(bar.bar ?? bar.index, index + 1),
          start_s: start,
          end_s: Math.max(end, start),
        };
      })
      .sort((left, right) => left.start_s - right.start_s);
  }

  if (!beats.length) {
    return [];
  }

  const barStarts = [];
  for (let index = 0; index < beats.length; index += 1) {
    const beat = beats[index];
    const next = beats[index + 1];
    if (index === 0 || beat.beat_in_bar === 1 || beat.bar !== beats[index - 1].bar) {
      barStarts.push({
        bar: asNumber(beat.bar, barStarts.length + 1),
        start_s: beat.time,
        end_s: next ? next.time : duration,
      });
    }
  }

  for (let index = 0; index < barStarts.length; index += 1) {
    const next = barStarts[index + 1];
    barStarts[index].end_s = next ? next.start_s : duration;
  }

  return barStarts;
}

function normalizeSections(sectionsArtifact, sectionsOutput, duration) {
  const sourceRows = asArray(sectionsArtifact?.sections).length ? asArray(sectionsArtifact?.sections) : asArray(sectionsOutput);
  return sourceRows
    .map((row, index) => {
      const start_s = startOf(row);
      const end_s = Math.max(endOf(row, duration), start_s);
      const sectionId = asString(row.section_id || row.id, `section-${String(index + 1).padStart(3, "0")}`);
      return {
        id: sectionId,
        start_s,
        end_s,
        label: asString(row.label || row.section_name, `Section ${index + 1}`),
        confidence: asNumber(row.confidence, 0),
        description: asString(row.description, ""),
      };
    })
    .sort(sortByStart);
}

function normalizeChords(harmonic, eventIndex) {
  const sourceRows = asArray(harmonic?.chords).length ? asArray(harmonic?.chords) : asArray(eventIndex?.chords);
  return sourceRows
    .map((row, index) => {
      const start_s = startOf(row);
      const end_s = Math.max(endOf(row, start_s), start_s);
      return {
        id: asString(row.id, `chord-${String(index + 1).padStart(3, "0")}`),
        label: asString(row.chord || row.label, "-"),
        start_s,
        end_s,
        confidence: asNumber(row.confidence, 0),
      };
    })
    .sort(sortByStart);
}

function normalizePatterns(patternsPayload, fallbackPayload) {
  const sourcePatterns = asArray(patternsPayload?.patterns).length ? asArray(patternsPayload?.patterns) : asArray(fallbackPayload?.patterns);
  const output = [];
  for (const pattern of sourcePatterns) {
    const occurrences = asArray(pattern.occurrences);
    for (let index = 0; index < occurrences.length; index += 1) {
      const row = occurrences[index];
      const start_s = startOf(row);
      const end_s = Math.max(endOf(row, start_s), start_s);
      output.push({
        id: `${asString(pattern.id, "pattern")}-${String(index + 1).padStart(3, "0")}`,
        pattern_id: asString(pattern.id, "pattern"),
        label: asString(pattern.label, pattern.id || "?"),
        occurrence_index: index + 1,
        occurrence_count: occurrences.length,
        start_s,
        end_s,
        start_bar: asNumber(row.start_bar, 0),
        end_bar: asNumber(row.end_bar, 0),
        sequence: asString(row.sequence || pattern.sequence, ""),
        bar_sequence: asString(row.bar_sequence || pattern.bar_sequence, ""),
      });
    }
  }
  return output.sort(sortByStart);
}

function normalizePhrases(eventIndex) {
  return asArray(eventIndex?.phrases)
    .map((row, index) => {
      const start_s = startOf(row);
      const end_s = Math.max(endOf(row, start_s), start_s);
      return {
        id: asString(row.phrase_window_id || row.id, `phrase-${String(index + 1).padStart(3, "0")}`),
        group_id: asString(row.phrase_group_id || row.group_id, ""),
        label: asString(row.phrase_window_id || row.label, `Phrase ${index + 1}`),
        section_id: asString(row.section_id, ""),
        start_s,
        end_s,
      };
    })
    .sort(sortByStart);
}

function normalizeEventRows(rows, fallbackCreatedBy = "") {
  return asArray(rows)
    .map((row, index) => {
      const start_s = startOf(row);
      const end_s = Math.max(endOf(row, start_s), start_s);
      const type = asString(row.type || row.label || row.identifier, "event");
      return {
        id: asString(row.id, `event-${String(index + 1).padStart(3, "0")}`),
        label: type,
        start_s,
        end_s,
        confidence: asNumber(row.confidence ?? row.intensity, 0),
        section_id: asString(row.section_id, ""),
        created_by: asString(row.created_by || row.model_name, fallbackCreatedBy),
        notes: row.notes || row.summary || row.evidence_summary || "",
        evidence: row.evidence,
        explanation: row.explanation,
        saliency: row.saliency,
      };
    })
    .sort(sortByStart);
}

function normalizeDrums(drumsPayload) {
  return asArray(drumsPayload?.events)
    .map((row, index) => {
      const time = asNumber(row.time, 0);
      return {
        id: asString(row.event_id || row.id, `drum-${String(index + 1).padStart(5, "0")}`),
        time,
        end_s: Math.max(asNumber(row.end_s, time), time),
        event_type: asString(row.event_type, "unresolved"),
      };
    })
    .sort((left, right) => left.time - right.time);
}

function normalizeEnergyRows(energyPayload, duration) {
  const beats = asArray(energyPayload?.beat_energy);
  if (!beats.length) {
    return [];
  }
  const rows = beats
    .map((beat, index) => {
      const start_s = asNumber(beat.time, 0);
      const next = beats[index + 1];
      const end_s = Math.max(asNumber(next?.time, duration), start_s);
      return {
        start_s,
        end_s,
        value: asNumber(beat.energy_score, 0),
      };
    })
    .sort(sortByStart);
  return rows;
}

function normalizeAccents(energyPayload, eventIndex) {
  const sourceRows = asArray(energyPayload?.accent_candidates).length ? asArray(energyPayload?.accent_candidates) : asArray(eventIndex?.accents);
  return sourceRows
    .map((row, index) => ({
      id: asString(row.id || row.accent_id, `accent-${String(index + 1).padStart(3, "0")}`),
      time: asNumber(row.time, 0),
      intensity: asNumber(row.intensity, 0),
      kind: asString(row.kind, "hit"),
    }))
    .sort((left, right) => left.time - right.time);
}

function normalizeTimeSeries(payload, fallbackSeconds) {
  const metadata = payload?.metadata || {};
  const intervalSeconds = asNumber(metadata.interval_ms, 0) / 1000 || asNumber(metadata.window_ms, 0) / 1000 || fallbackSeconds;
  const frames = asArray(payload?.frames).map((row, index) => {
    const start_s = asNumber(row.start_s ?? row.time ?? 0, index * intervalSeconds);
    const end_s = Math.max(asNumber(row.end_s, start_s + intervalSeconds), start_s);
    return {
      ...row,
      start_s,
      end_s,
    };
  });

  return {
    ...payload,
    intervalSeconds,
    windowSeconds: intervalSeconds,
    frames,
  };
}

function buildEventComparisons(machineEvents, timelineEvents) {
  const machineById = new Map(machineEvents.map((event) => [event.id, event]));
  const timelineById = new Map(timelineEvents.map((event) => [event.id, event]));
  const comparisons = [];

  for (const [id, machine] of machineById) {
    const output = timelineById.get(id);
    if (!output) {
      comparisons.push({ id, status: "not_exported", start_s: machine.start_s, end_s: machine.end_s });
      continue;
    }

    const sameStart = Math.abs(machine.start_s - output.start_s) <= 0.001;
    const sameEnd = Math.abs(machine.end_s - output.end_s) <= 0.001;
    comparisons.push({
      id,
      status: sameStart && sameEnd ? "exact" : "shifted",
      start_s: Math.min(machine.start_s, output.start_s),
      end_s: Math.max(machine.end_s, output.end_s),
    });
    timelineById.delete(id);
  }

  for (const [id, output] of timelineById) {
    comparisons.push({ id, status: "output_only", start_s: output.start_s, end_s: output.end_s });
  }

  return comparisons.sort(sortByStart);
}

function buildValidationDrift(beatsArtifact, beatsOutput) {
  const referenceBeats = asArray(beatsArtifact?.beats);
  const outputBeats = asArray(beatsOutput);
  if (!referenceBeats.length || !outputBeats.length) {
    return [];
  }

  const rows = [];
  const length = Math.min(referenceBeats.length, outputBeats.length);
  for (let index = 0; index < length; index += 1) {
    const referenceTime = asNumber(referenceBeats[index].time, 0);
    const inferredTime = asNumber(outputBeats[index].time, referenceTime);
    const delta = inferredTime - referenceTime;
    rows.push({
      reference_time: referenceTime,
      inferred_time: inferredTime,
      delta_seconds: delta,
      within_tolerance: Math.abs(delta) <= 0.06,
    });
  }

  return rows;
}

function resolveDuration(beats, sections, fallbackDuration) {
  const beatMax = beats.at(-1)?.time || 0;
  const sectionMax = sections.reduce((maxValue, row) => Math.max(maxValue, asNumber(row.end_s, 0)), 0);
  return Math.max(asNumber(fallbackDuration, 0), beatMax, sectionMax);
}

export function buildTimelineData(data) {
  const beatsArtifact = data?.beatsArtifact || {};
  const beatsOutput = data?.beatsOutput || [];
  const sectionsArtifact = data?.sectionsArtifact || {};
  const sectionsOutput = data?.sectionsOutput || [];
  const harmonic = data?.harmonic || {};
  const patterns = data?.patterns || {};
  const patternMining = data?.patternMining || {};
  const eventIndex = data?.eventIndex || {};
  const energy = data?.energy || {};
  const drumsPayload = data?.drums || {};

  const beats = normalizeBeats(beatsArtifact, beatsOutput);
  const sections = normalizeSections(sectionsArtifact, sectionsOutput, asNumber(beatsArtifact.duration, 0));
  const duration = resolveDuration(beats, sections, beatsArtifact.duration);
  const bars = buildBars(beats, beatsArtifact.bars, duration);

  const chords = normalizeChords(harmonic, eventIndex);
  const patternsRows = normalizePatterns(patterns, patternMining);
  const phrases = normalizePhrases(eventIndex);

  const identifierHints = normalizeEventRows(data?.identifierHints?.events, "energy_identifier");
  const machineEvents = normalizeEventRows(data?.eventMachine?.events || data?.eventRules?.events, "machine");
  const mlEvents = normalizeEventRows(data?.eventMl?.events, "ml");
  const outputTimelineEvents = normalizeEventRows(data?.eventsTimeline?.events, "timeline");

  const drums = normalizeDrums(drumsPayload);
  const energyRows = normalizeEnergyRows(energy, duration);
  const accentCandidates = normalizeAccents(energy, eventIndex);

  const eventComparisons = buildEventComparisons(machineEvents, outputTimelineEvents);
  const validationDrift = buildValidationDrift(beatsArtifact, beatsOutput);

  const fftBands = normalizeTimeSeries(data?.fftBands || {}, 0.05);
  const rmsLoudness = normalizeTimeSeries(data?.rmsLoudness || {}, 0.01);
  const loudnessEnvelope = normalizeTimeSeries(data?.loudnessEnvelope || {}, 0.2);

  return {
    duration,
    bpm: asNumber(beatsArtifact.bpm ?? beatsArtifact.tempo, 0),
    beats,
    bars,
    sections,
    chords,
    patterns: patternsRows,
    phrases,
    identifierHints,
    machineEvents,
    mlEvents,
    drums,
    energyRows,
    accentCandidates,
    eventComparisons,
    validationDrift,
    fftBands,
    rmsLoudness,
    loudnessEnvelope,
  };
}
