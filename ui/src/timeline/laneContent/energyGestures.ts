// energyGestures.ts — Character, Energy Level, Tension Shape and Gestures
// lane adapters (texture and intensity candidates, plus the shipped gesture
// timeline). Split out of laneContent.ts (v3.9 item 7) with no behaviour
// change; see laneContent.ts for the dispatch table and shared SparseBlock
// type. Character is grouped here rather than with the section-structure
// family because it shares the same texture/intensity axis as Energy Level
// and Tension Shape, not a structural claim.

import type { EventTimeline } from "../../data/types";
import type {
  CharacterFile,
  EnergyLevelFile,
  TensionShapeFile,
} from "../../data/sparseArtifacts";
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
 * Candidate `energy` (1-5) producer from `experiments/energy_level` (item
 * 5/6) — segment mix loudness + arrangement_state stems-playing fraction,
 * song-relative quintile-binned. A proposal to audition, not ground truth.
 */
export function energyLevelContent(file: EnergyLevelFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => ({
    id: `energy-level-${i + 1}`,
    start_s: b.start_s,
    end_s: b.end_s,
    label: "",
    wideLabel: `energy ${b.energy}`,
    laneLabel: "Energy Level",
    caption: `${formatRange(b.start_s, b.end_s)} · energy ${b.energy} · confidence ${round(b.confidence, 2)}`,
    reference: `energy-level-${i + 1}`,
    detail: `mix ${round(b.evidence.mix_mean, 3)} · stems ${round(b.evidence.stems_fraction, 2)}`,
    summary: "experiments/energy_level — 0.5*mix loudness + 0.5*stems-playing fraction, song-relative quintile -> 1-5. Candidate for sections.json's energy.",
    raw: b,
  }));
}

/**
 * Candidate `tension` (1-5) producer from `experiments/tension_shape` (item
 * 5/6) — energy slope + gesture build/tension overlap + phrase_periodicity
 * through-composed regime overlap. A proposal to audition, not ground truth.
 */
export function tensionShapeContent(file: TensionShapeFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const bumps = [
      b.evidence.gesture_bump ? "gesture" : null,
      b.evidence.phrase_periodicity_through_composed_bump ? "through-composed" : null,
    ].filter(Boolean);
    const bumpText = bumps.length ? `+${bumps.join("+")}` : "no bump";
    return {
      id: `tension-shape-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: "",
      wideLabel: `tension ${b.tension}`,
      laneLabel: "Tension Shape",
      caption: `${formatRange(b.start_s, b.end_s)} · tension ${b.tension} · ${bumpText}`,
      reference: `tension-shape-${i + 1}`,
      detail: `slope ${round(b.evidence.slope, 3)} · confidence ${round(b.confidence, 2)}`,
      summary: "experiments/tension_shape — mix-loudness slope, song-relative quintile -> 1-5, +1 gesture overlap, +1 through-composed regime overlap. Candidate for sections.json's tension.",
      raw: b,
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
