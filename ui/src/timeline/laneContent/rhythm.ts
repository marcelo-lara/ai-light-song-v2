// rhythm.ts — Rhythm Drum IOI, Rhythm Stem Autocorr and Rhythm Vocal Onsets
// candidate producers. Split out of laneContent.ts (v3.9 item 7) with no
// behaviour change; see laneContent.ts for the dispatch table and shared
// SparseBlock type.

import type {
  RhythmDrumIoiFile,
  RhythmStemAutocorrFile,
  RhythmVocalOnsetsFile,
} from "../../data/sparseArtifacts";
import type { SparseBlock } from "../laneContent";
import { formatRange, round } from "./shared";

/** Compact `source:subdivision` list, `"—"` when a row carries no sources. */
function subdivisionSummary(subs: Record<string, string>): string {
  const entries = Object.entries(subs);
  if (entries.length === 0) return "—";
  return entries.map(([k, v]) => `${k}:${v}`).join(" ");
}

/**
 * Candidate `rhythm.drums` producer from `experiments/rhythm_drum_ioi` (item
 * 5/6a) — dominant `drum_events.json` inter-onset interval / local beat
 * period -> nearest subdivision. A proposal to audition, not ground truth.
 */
export function rhythmDrumIoiContent(file: RhythmDrumIoiFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => ({
    id: `rhythm-drum-ioi-${i + 1}`,
    start_s: b.start_s,
    end_s: b.end_s,
    label: "",
    wideLabel: subdivisionSummary(b.subdivisions),
    laneLabel: "Rhythm Drum IOI",
    caption: `${formatRange(b.start_s, b.end_s)} · ${subdivisionSummary(b.subdivisions)} · ${round(b.onsets_per_bar, 2)}/bar`,
    reference: `rhythm-drum-ioi-${i + 1}`,
    detail: `confidence ${Object.entries(b.confidence).map(([k, v]) => `${k}:${round(v, 2)}`).join(" ")}`,
    summary: "experiments/rhythm_drum_ioi — median drum-event IOI / local beat period -> nearest subdivision. Candidate for sections.json's rhythm.drums.",
    raw: b,
  }));
}

/**
 * Candidate `rhythm.{drums,bass,harmonic,vocals}` producer from
 * `experiments/rhythm_stem_autocorr` (item 5/6b) — sub-beat autocorrelation
 * of each stem's 20 ms loudness. A proposal to audition, not ground truth.
 */
export function rhythmStemAutocorrContent(file: RhythmStemAutocorrFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => ({
    id: `rhythm-stem-autocorr-${i + 1}`,
    start_s: b.start_s,
    end_s: b.end_s,
    label: "",
    wideLabel: subdivisionSummary(b.subdivisions),
    laneLabel: "Rhythm Stem Autocorr",
    caption: `${formatRange(b.start_s, b.end_s)} · ${subdivisionSummary(b.subdivisions)}`,
    reference: `rhythm-stem-autocorr-${i + 1}`,
    detail: `confidence ${Object.entries(b.confidence).map(([k, v]) => `${k}:${round(v, 2)}`).join(" ")}`,
    summary: "experiments/rhythm_stem_autocorr — per-stem sub-beat loudness autocorrelation -> nearest subdivision. Candidate for sections.json's rhythm.* fields.",
    raw: b,
  }));
}

/**
 * Candidate `rhythm.vocals` + `onsets_per_beat` producer from
 * `experiments/rhythm_vocal_onsets` (item 5/6c) — dominant whisper
 * word-onset interval / local beat period. `compute` runs only in the
 * ACE-Step sandbox image. A proposal to audition, not ground truth.
 */
export function rhythmVocalOnsetsContent(file: RhythmVocalOnsetsFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const opb = b.onsets_per_beat == null ? "no onsets" : `${round(b.onsets_per_beat, 2)}/beat`;
    return {
      id: `rhythm-vocal-onsets-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: "",
      wideLabel: subdivisionSummary(b.subdivisions),
      laneLabel: "Rhythm Vocal Onsets",
      caption: `${formatRange(b.start_s, b.end_s)} · ${subdivisionSummary(b.subdivisions)} · ${opb}`,
      reference: `rhythm-vocal-onsets-${i + 1}`,
      detail: `confidence ${Object.entries(b.confidence).map(([k, v]) => `${k}:${round(v, 2)}`).join(" ")}`,
      summary: "experiments/rhythm_vocal_onsets — median whisper word-onset IOI / local beat period -> nearest subdivision. Candidate for sections.json's rhythm.vocals.",
      raw: b,
    };
  });
}
