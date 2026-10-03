// characterGestures.ts — Character and Gestures lane adapters (the texture
// candidate, plus the shipped gesture timeline). Split out of laneContent.ts
// (v3.9 item 7); see laneContent.ts for the dispatch table and shared
// SparseBlock type.

import type { EventTimeline } from "../../data/types";
import type { BarFeaturesFile, CharacterFile, DownbeatReanchorFile, FilterSweepFile, FilterSweepV2File, LightChangesFile, PhrasesFile } from "../../data/sparseArtifacts";
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

const AFTERMATH_TINT: Record<string, string> = {
  gap: "filterSweepV2Gap",
  drop: "filterSweepV2Drop",
  break: "filterSweepV2Break",
};

/**
 * Filter sweeps v2 from `experiments/filter_sweep_v2` — a run of bars where the
 * harmonic stem's high/low band ratio or rolloff moves consistently. The block
 * spans the run; its end (on the beat grid, `end_time`) is the cue, and the
 * aftermath says what the next 1-2 bars do. `none` = nothing follows, a suspect
 * detection (lower confidence, grey). A proposal to audition, not ground truth.
 */
export function filterSweepV2Content(file: FilterSweepV2File | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const conf = b.confidence == null ? "no confidence reported" : `confidence ${round(b.confidence, 2)}`;
    const hl = b.hl_change_db == null ? "hl n/a" : `${round(b.hl_change_db, 1)} dB`;
    const roll = b.roll_change_oct == null ? "rolloff n/a" : `${round(b.roll_change_oct, 2)} oct`;
    const endBar = b.end_bar == null ? "song end" : `bar ${b.end_bar}`;
    return {
      id: `filter-sweep-v2-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: b.aftermath === "none" ? b.direction : `${b.direction} → ${b.aftermath}`,
      wideLabel: `${b.direction} · bars ${b.start_bar}-${b.end_bar ?? "end"} · ends ${b.end_kind} → ${b.aftermath}`,
      laneLabel: "Filter Sweeps v2",
      caption: `${formatRange(b.start_s, b.end_s)} · ${b.direction} · end ${round(b.end_time, 2)} s (${endBar}) ${b.end_kind} · aftermath ${b.aftermath}`,
      reference: `filter-sweep-v2-${i + 1}`,
      detail: `${hl}, ${roll}, consistency ${round(b.consistency, 2)}`,
      summary: `experiments/filter_sweep_v2 — ${b.direction} over bars ${b.start_bar}-${b.end_bar ?? "end"}: high/low ratio ${hl}, ` +
        `rolloff ${roll}; end at ${round(b.end_time, 2)} s is a ${b.end_kind}, aftermath ${b.aftermath}` +
        `${b.aftermath === "none" ? " (nothing follows: suspect)" : ""}; ${conf}.`,
      tintId: AFTERMATH_TINT[b.aftermath] ?? "filterSweepV2None",
      raw: b,
    };
  });
}

const fx = (v: number | null, d = 3): string => (v == null ? "n/a" : String(round(v, d)));

/**
 * Per-bar table from the published `bar_features.json` — one block per bar,
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
    const kick = b.kick_present == null ? "kick n/a" : b.kick_present ? "kick" : "no kick";
    const tint = b.irregular
      ? "barFeaturesIrregular"
      : b.brightness == null || b.brightness < lo
        ? "barFeaturesLow"
        : b.brightness >= hi
          ? "barFeaturesHigh"
          : "barFeaturesMid";
    const slip = b.irregular ? " · not 4 beats" : "";
    return {
      id: `bar-features-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: String(b.bar),
      wideLabel: `${b.bar} · ${kick} · br ${fx(b.brightness, 2)}${slip}`,
      laneLabel: "Bar Features",
      caption: `bar ${b.bar} ${formatRange(b.start_s, b.end_s)} · brightness ${fx(b.brightness, 2)} ` +
        `· transient density ${fx(b.transient_density)} · ${kick}${slip}`,
      reference: `bar-features-${i + 1}`,
      detail: [
        b.sweep_state ? `sweep ${b.sweep_state}` : "",
        b.light_change_role ? `light change: ${b.light_change_role}` : "",
      ].filter(Boolean).join(" · "),
      summary: `bar_features.json — bar ${b.bar}` +
        (b.irregular ? " (not 4 beats: grid slip, flagged not repaired)" : "") +
        `: brightness ${fx(b.brightness, 2)}, transient density ${fx(b.transient_density)}, ${kick}.`,
      tintId: tint,
      raw: b,
    };
  });
}

const ROLE_TINT: Record<string, string> = {
  groove_in: "lightChangeGrooveIn",
  build: "lightChangeBuild",
  break: "lightChangeBreak",
  drop: "lightChangeDrop",
  gap: "lightChangeGap",
  fill: "lightChangeFill",
};

/**
 * Light change points from the published `song_event_timeline.json`
 * `light_change` rows — one marker per point, labelled with its role, tinted
 * per role. A point has no duration (`end_time` = `start_time`), so the block is
 * the minimum-width marker at the point's time. `confidence` is `null`: the
 * point score is uncalibrated, and none is invented.
 */
export function lightChangesContent(file: LightChangesFile | null): SparseBlock[] {
  return (file?.points ?? []).map((p, i) => ({
    id: `light-change-${i + 1}`,
    start_s: p.start_time,
    end_s: p.end_time,
    label: p.role,
    wideLabel: p.role,
    laneLabel: "Light Changes",
    caption: `${formatRange(p.start_time, p.end_time)} · ${p.role}`,
    reference: `light-change-${i + 1}`,
    detail: p.section_id ? `in ${p.section_id}` : "between published sections",
    summary: `song_event_timeline.json — light_change ${p.role} at ${round(p.start_time, 2)} s; no confidence (score is not calibrated).`,
    tintId: ROLE_TINT[p.role] ?? "lightChangeUnknown",
    raw: p,
  }));
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

/**
 * Re-anchored bar labels from `experiments/downbeat_reanchor` — one block per bar, label = the
 * re-anchored bar number. Beat times are unchanged; only which beat is the downbeat moves. Grey
 * when the downbeat carries no confidence (local anchors disagree, or none). A proposal to
 * audition, not truth.
 */
export function downbeatReanchorContent(file: DownbeatReanchorFile | null): SparseBlock[] {
  return (file?.bars ?? []).map((b, i) => {
    const conf = b.downbeat_confidence == null ? "no confidence (unresolved)" : `confidence ${round(b.downbeat_confidence, 2)}`;
    const len = b.irregular ? ` · ${b.beats_in_bar} beats (song edge or off-grid)` : "";
    return {
      id: `downbeat-reanchor-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: String(b.bar),
      wideLabel: `${b.bar} · ${b.resolved ? "resolved" : "unresolved"}${len}`,
      laneLabel: "Downbeat Reanchor",
      caption: `bar ${b.bar} ${formatRange(b.start_s, b.end_s)} · ${conf}${len}`,
      reference: `downbeat-reanchor-${i + 1}`,
      detail: `${b.beats_in_bar} beats`,
      summary: "experiments/downbeat_reanchor — bar labels rebuilt from anchor votes on unchanged beat times; confidence null where anchors disagree or none exist. Proposal to audition, not truth.",
      tintId: b.resolved ? "downbeatReanchor" : "downbeatReanchorUnresolved",
      raw: b,
    };
  });
}
