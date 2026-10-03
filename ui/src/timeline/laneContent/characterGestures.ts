// characterGestures.ts — Character and Gestures lane adapters (the texture
// candidate, plus the shipped gesture timeline). Split out of laneContent.ts
// (v3.9 item 7); see laneContent.ts for the dispatch table and shared
// SparseBlock type.

import type { EventTimeline } from "../../data/types";
import type { BarFeaturesFile, CharacterFile, FilterSweepFile, PhrasesFile } from "../../data/sparseArtifacts";
import type { SparseBlock } from "../laneContent";
import { formatRange, round } from "./shared";

/**
 * Character blocks — what a passage is *like*, not where it sits in the form.
 *
 * The lane exists because the operator already works this way: `Armin -
 * Revolution` carries a hand-marked "Breath" block ("Vocal - no intense
 * section") with its own fixture behaviour, and it is not a section boundary.
 * Blocks are tinted by kind, so the texture of a song reads as a colour strip
 * before any label does, and each one names the sources that had to agree.
 */
export function characterContent(file: CharacterFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b) => {
    const evidence = Object.entries(b.evidence)
      .map(([key, value]) => `${key.replace(/_z$/, "")} ${round(value, 2)}`)
      .join(", ");
    const shadow = b.kind.startsWith("shadow ");
    return {
      id: b.id,
      start_s: b.start_s,
      end_s: b.end_s,
      label: b.kind,
      wideLabel: `${b.kind} · ${b.source}${evidence ? ` · ${evidence}` : ""}`,
      // `vocal lead` -> characterVocalLead, `breath` -> characterBreath.
      tintId: `character${
        shadow
          ? "Shadow"
          : b.kind.replace(/(?:^|\s)(.)/g, (_, c: string) => c.toUpperCase())
      }`,
      laneLabel: "Character",
      caption: `${formatRange(b.start_s, b.end_s)} · ${b.source}`,
      reference: b.id,
      detail: b.source,
      summary: shadow
        ? `allin1's frame-level posterior holds sustained mass on \`${b.kind.slice(7)}\` here, a label its own published segmentation never used anywhere in this song — a character the 8-bar argmax could not express.`
        : `${b.kind} passage${
            b.source === "stems+clap"
              ? ", from the stems plus CLAP's calm/intense axis"
              : ", from the stems alone"
          }${evidence ? `: ${evidence}` : ""}.`,
      raw: b.raw,
    };
  });
}

/**
 * Named gesture phases (approach/build/tension/impact/release) and
 * section-pair transitions ("<from> → <to>") from `song_event_timeline.json`
 * -- the production `gestures` stage (plan v3.0 item 9, replacing the
 * Machine Events / Identifier Hints lanes it superseded). Never claims a
 * "drop" by name (a drop is derived from a named section pair, never detected); each row is already flat, so one block
 * is one phase or one transition, never a nested composite.
 */
export function gesturesContent(file: EventTimeline | null): SparseBlock[] {
  return (file?.events ?? []).map((e, i) => {
    const id = `gesture-event-${String(i + 1).padStart(3, "0")}`;
    const end_s = Math.max(e.end_time, e.start_time + 0.1);
    return {
      id,
      start_s: e.start_time,
      end_s,
      label: e.type,
      wideLabel: `${e.type} · conf ${round(e.confidence, 2)} · intensity ${round(e.intensity, 2)}`,
      laneLabel: "Gestures",
      caption: `${formatRange(e.start_time, e.end_time)} · conf ${round(e.confidence, 2)}`,
      reference: id,
      detail: e.section_id ?? "-",
      summary: e.summary || e.evidence_summary || `${e.type} at ${round(e.start_time, 2)}s.`,
      raw: e,
    };
  });
}

/**
 * Filter sweeps from `experiments/filter_sweep` — a harmonic or bass stem
 * opening (brighter) or closing (darker) over 2-16 bars while its loudness
 * stays level. Distinct from the Gestures lane's riser (a new sound getting
 * louder in the high bands). A proposal to audition, not ground truth.
 */
export function filterSweepContent(file: FilterSweepFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const conf = b.confidence == null ? "no confidence reported" : `confidence ${round(b.confidence, 2)}`;
    return {
      id: `filter-sweep-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: b.direction,
      wideLabel: `${b.direction} · ${b.stem} · ${round(b.depth, 1)} oct`,
      laneLabel: "Filter Sweeps",
      caption: `${formatRange(b.start_s, b.end_s)} · ${b.stem} ${b.direction} · ${round(b.depth, 2)} oct`,
      reference: `filter-sweep-${i + 1}`,
      detail: `${b.stem} ${b.direction}`,
      summary: `experiments/filter_sweep — ${b.stem} stem ${b.direction}: spectral centroid moved ` +
        `${round(b.depth, 2)} octaves over ${round(b.end_s - b.start_s, 1)} s with the stem's loudness level; ${conf}.`,
      tintId: b.direction === "closing" ? "filterSweepClosing" : "filterSweepOpening",
      raw: b,
    };
  });
}

const fx = (v: number | null, d = 3): string => (v == null ? "n/a" : String(round(v, d)));

/**
 * Per-bar feature table from `experiments/bar_features` — one block per bar,
 * tinted by the bar's brightness tercile within the song (grey when the bar is
 * not 4 beats long: a known grid slip, flagged and never repaired). The label
 * is the bar number; the caption carries the numbers. A feature table to read
 * against the other lanes, not a claim.
 */
export function barFeaturesContent(file: BarFeaturesFile | null): SparseBlock[] {
  const bars = file?.bars ?? [];
  const br = bars.map((b) => b.brightness).filter((v): v is number => v != null).sort((a, b) => a - b);
  const lo = br.length ? br[Math.floor(br.length / 3)]! : 0;
  const hi = br.length ? br[Math.floor((2 * br.length) / 3)]! : 0;
  return bars.map((b, i) => {
    const drums = `k${b.kick} s${b.snare} h${b.hat}`;
    const tint = b.irregular
      ? "barFeaturesIrregular"
      : b.brightness == null || b.brightness < lo
        ? "barFeaturesLow"
        : b.brightness >= hi
          ? "barFeaturesHigh"
          : "barFeaturesMid";
    const slip = b.irregular ? ` · ${b.beats_in_bar} beats (not 4)` : "";
    const arrange = [
      b.entered.length ? `in: ${b.entered.join(",")}` : "",
      b.left.length ? `out: ${b.left.join(",")}` : "",
    ].filter(Boolean).join(" ");
    return {
      id: `bar-features-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: String(b.bar),
      wideLabel: `${b.bar} · ${drums} · br ${fx(b.brightness, 2)}${slip}`,
      laneLabel: "Bar Features",
      caption: `bar ${b.bar} ${formatRange(b.start_s, b.end_s)} · mix ${fx(b.mix_rms)} bass ${fx(b.bass_rms)} ` +
        `drums ${fx(b.drums_rms)} harm ${fx(b.harmonic_rms)} voc ${fx(b.vocals_rms)} · brightness ${fx(b.brightness, 2)} ` +
        `· transient ${fx(b.transient_mean)}±${fx(b.transient_std)} · ${drums}${slip}`,
      reference: `bar-features-${i + 1}`,
      detail: [arrange, b.sweep_opening > 0 ? `sweep opening ${pct(b.sweep_opening)}` : "",
        b.sweep_closing > 0 ? `sweep closing ${pct(b.sweep_closing)}` : "",
        b.gestures.length ? `gestures: ${b.gestures.join(", ")}` : "",
        `vocals ${pct(b.vocals_cover)}`].filter(Boolean).join(" · "),
      summary: `experiments/bar_features — bar ${b.bar}, ${b.beats_in_bar} beats` +
        (b.irregular ? " (not 4: grid slip, flagged not repaired)" : "") +
        `: RMS mix ${fx(b.mix_rms)}, brightness ${fx(b.brightness, 2)}, ${drums}, vocals cover ${pct(b.vocals_cover)}.`,
      tintId: tint,
      raw: b,
    };
  });
}

const pct = (v: number | null): string => (v == null ? "n/a" : `${Math.round(v * 100)}%`);
const yn = (v: boolean | null): string => (v == null ? "n/a" : v ? "yes" : "no");

/**
 * Phrases from `experiments/phrases` — the song cut where the audio changes
 * (stem entries/exits, impacts, pre-drop gaps, riser and snare-roll ends), each
 * edge at the nearest trusted beat. Never bar-counted. `resolved: false`
 * blocks are tinted apart: the evidence for one of their edges disagrees. A
 * proposal to audition, not ground truth.
 */
export function phrasesContent(file: PhrasesFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const n = i + 1;
    const conf = b.confidence == null ? "no confidence reported" : `confidence ${round(b.confidence, 2)}`;
    const presence = [
      b.kick_presence != null && b.kick_presence >= 0.5 ? "kick" : null,
      b.bass_presence != null && b.bass_presence >= 0.5 ? "bass" : null,
      b.vocals_presence != null && b.vocals_presence >= 0.5 ? "vox" : null,
    ].filter((x): x is string => x != null);
    const flags = [
      b.ends_on_gap ? "ends on gap" : null,
      b.kick_dropout_near_end ? "kick drops out" : null,
      b.noise_sweep ? "noise sweep" : null,
      b.repeat_of ? `repeats ${b.repeat_of}` : null,
    ].filter((x): x is string => x != null);
    const sweeps = b.filter_sweeps == null ? "filter sweeps n/a" : `${b.filter_sweeps.length} filter sweep(s)`;
    const state = b.resolved ? "resolved" : `UNRESOLVED (${b.conflicts.join("; ")})`;
    return {
      id: `phrases-${n}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: b.resolved ? `${n}` : `${n}?`,
      wideLabel: `${n}${b.resolved ? "" : "?"} · ${presence.length ? presence.join("+") : "bare"}${flags.length ? ` · ${flags[0]}` : ""}`,
      laneLabel: "Phrases",
      caption: `${formatRange(b.start_s, b.end_s)} · ${presence.join("+") || "no kick/bass/vox"} · ${state}`,
      reference: `phrases-${n}`,
      detail: presence.join("+") || "bare",
      summary:
        `experiments/phrases — ${b.n_beats} beats; kick ${pct(b.kick_presence)}, bass ${pct(b.bass_presence)}, ` +
        `vocals ${pct(b.vocals_presence)}; riser ${pct(b.riser_density)}, snare roll ${pct(b.snare_roll_density)}; ` +
        `${sweeps}; noise sweep ${yn(b.noise_sweep)}; kick drops out near end ${yn(b.kick_dropout_near_end)}; ` +
        `ends on gap ${yn(b.ends_on_gap)}; ${b.repeat_of ? `repeats ${b.repeat_of}` : "no earlier repeat"}; ` +
        `${state}; ${conf}.`,
      tintId: b.resolved ? "phrases" : "phrasesUnresolved",
      raw: b,
    };
  });
}
