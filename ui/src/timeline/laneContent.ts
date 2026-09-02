// laneContent.ts — per-lane content adapters for SparseLane.
//
// Ported from the previous app's src/lib/timeline/sparseContent.js. Each adapter is a pure
// function from a loaded artifact payload to an ordered `SparseBlock[]`; the
// blocks carry everything the item-6 block inspector needs (`label`,
// `laneLabel`, `caption`, `reference`, `detail`, `summary`) plus the raw source
// row so the inspector's "show raw" disclosure works.
//
// `buildLaneBlocks(laneId, sources)` dispatches to the right adapter; the
// individual adapters are exported for unit tests against artifact fixtures.

import type { HumanHintsFile, HarmonicLayer, SectionRow } from "../data/types";
import type {
  DropProposalsFile,
  EventsFile,
  PatternsFile,
  SymbolicPhrasesFile,
} from "../data/sparseArtifacts";

import { romanNumeral } from "./romanNumeral";

export interface SparseBlock {
  id: string;
  start_s: number;
  end_s: number;
  /** default block label */
  label: string;
  /** label variant drawn when the block is wide (e.g. chord + roman numeral) */
  wideLabel?: string;
  /**
   * Optional per-block tint id, overriding the lane's own tint. Used by the
   * Drop Proposals lane to colour a candidate that already matches a human
   * label differently from one still needing a decision.
   */
  tintId?: string;
  laneLabel: string;
  caption: string;
  reference: string;
  detail: string;
  summary: string;
  /** original artifact row — surfaced by the inspector's raw disclosure */
  raw: unknown;
}

// -- formatting (ported from the previous app's src/lib/utils.js) ------------------------

function fmtTime(seconds: number): string {
  const n = Number(seconds);
  if (!Number.isFinite(n)) return "-";
  const m = Math.floor(n / 60);
  return `${m}:${(n - m * 60).toFixed(1).padStart(4, "0")}`;
}

export function formatRange(start: number, end: number): string {
  return `${fmtTime(start)}–${fmtTime(end)}`;
}

function round(v: number | null | undefined, digits = 2): string {
  return v == null || !Number.isFinite(Number(v)) ? "-" : Number(v).toFixed(digits);
}

// -- adapters --------------------------------------------------------------

export function humanHintsContent(file: HumanHintsFile | null): SparseBlock[] {
  return (file?.human_hints ?? []).map((h) => ({
    id: h.id,
    start_s: h.start_time,
    end_s: h.end_time,
    label: h.title || h.id,
    laneLabel: "Human Hints",
    caption: `${formatRange(h.start_time, h.end_time)}${
      h.lighting_hint ? ` · ${h.lighting_hint}` : ""
    }`,
    reference: h.id,
    detail: h.lighting_hint || "-",
    summary: h.summary || "Reference hint window from human annotation.",
    raw: h,
  }));
}

/**
 * Drop-impact proposals from `experiments/drop_detection`. These are candidates
 * to audition, not findings: the label leads with whether the candidate already
 * matches a hand-authored `drop impact` (`✓`) or is unconfirmed (`?`), then
 * names the role-change channels that fired, which is what you need in order to
 * judge it against what you are hearing.
 */
export function dropProposalsContent(file: DropProposalsFile | null): SparseBlock[] {
  return (file?.proposals ?? []).map((p) => {
    const matched = p.matches_human_label != null;
    const channels = p.channels.join(" · ") || "no channel";
    const evidence = Object.entries(p.evidence)
      .map(([key, value]) => `${key.replace(/_db$/, "")} ${value > 0 ? "+" : ""}${round(value, 1)} dB`)
      .join(", ");
    return {
      id: p.id,
      start_s: p.start_s,
      end_s: p.end_s,
      label: `${matched ? "✓" : "?"} ${channels}`,
      // Confirmed candidates go teal and unconfirmed ones stay magenta, so the
      // lane reads as a triage queue at song-overview zoom, where the 0.5 s
      // blocks are far too narrow for their labels.
      ...(matched ? { tintId: "dropProposalsMatched" } : {}),
      wideLabel: `${matched ? "✓" : "?"} ${channels}${evidence ? ` · ${evidence}` : ""}`,
      laneLabel: "Drop Proposals",
      caption: `${formatRange(p.start_s, p.end_s)} · ${
        matched
          ? `matches human ${round(p.matches_human_label, 2)}s`
          : "unconfirmed"
      }`,
      reference: p.id,
      detail: channels,
      summary: `Stage-1 drop-impact candidate fired by ${channels}${
        evidence ? `; ${evidence}` : ""
      }. ${
        matched
          ? `Already within 0.5 s of the human label at ${round(p.matches_human_label, 2)}s.`
          : "Not yet in human_hints.json — audition it, then copy it across by hand if it is real."
      }`,
      raw: p.raw ?? p,
    };
  });
}

export function sectionsContent(rows: readonly SectionRow[]): SparseBlock[] {
  return rows.map((s, i) => ({
    id: s.section_id ?? `section-${String(i + 1).padStart(3, "0")}`,
    start_s: s.start,
    end_s: s.end,
    label: s.form_role ?? s.label,
    laneLabel: "Sections",
    caption: `${formatRange(s.start, s.end)}${
      s.confidence != null ? ` · conf ${round(s.confidence)}` : ""
    }`,
    reference: s.section_id ?? "-",
    detail: s.energy_character ?? s.repetition_group ?? "-",
    summary:
      s.description ||
      "Section navigation stays browser-local and moves only the shared playback cursor.",
    raw: s,
  }));
}

export function chordsContent(harmonic: HarmonicLayer | null): SparseBlock[] {
  const key = harmonic?.global_key?.label ?? null;
  return (harmonic?.chords ?? []).map((c, i) => {
    const roman = romanNumeral(c.chord, key);
    return {
      id: `chord-${String(i + 1).padStart(3, "0")}`,
      start_s: c.time,
      end_s: c.end_s,
      label: c.chord || "-",
      ...(roman ? { wideLabel: `${c.chord} · ${roman}` } : {}),
      laneLabel: "Chord Regions",
      caption: `${formatRange(c.time, c.end_s)}${
        c.confidence != null ? ` · conf ${round(c.confidence)}` : ""
      }`,
      reference: roman ?? "-",
      detail:
        c.bar != null ? `bar ${c.bar}${c.beat != null ? `.${c.beat}` : ""}` : "-",
      summary: `Chord ${c.chord}${roman ? ` (${roman} in ${key})` : ""} from the Layer A harmonic read.`,
      raw: c,
    };
  });
}

export function patternsContent(file: PatternsFile | null): SparseBlock[] {
  return (file?.occurrences ?? []).map((p) => ({
    id: p.id,
    start_s: p.start_s,
    end_s: p.end_s,
    label: `Pattern ${p.label}`,
    laneLabel: "Pattern Occurrences",
    caption: `${formatRange(p.start_s, p.end_s)} · bars ${p.start_bar}-${p.end_bar}`,
    reference: p.pattern_id,
    detail: p.bar_sequence || p.sequence || `bars ${p.start_bar}-${p.end_bar}`,
    summary: `Occurrence ${p.occurrence_index} of ${p.occurrence_count} for ${p.pattern_id} spans bars ${p.start_bar}-${p.end_bar}${
      p.sequence ? ` with progression ${p.sequence}.` : "."
    }`,
    raw: p,
  }));
}

function eventContent(
  file: EventsFile | null,
  laneLabel: string,
  fallbackSummary: string,
): SparseBlock[] {
  return (file?.events ?? []).map((e) => ({
    id: e.id,
    start_s: e.start_s,
    end_s: e.end_s,
    label: String(e.label),
    laneLabel,
    caption: `${formatRange(e.start_s, e.end_s)}${
      e.confidence != null ? ` · conf ${round(e.confidence)}` : ""
    }`,
    reference: e.id,
    detail: e.section_id ?? e.created_by ?? "-",
    summary: e.evidence_summary || e.notes || fallbackSummary,
    raw: e.raw ?? e,
  }));
}

export const identifierHintsContent = (file: EventsFile | null): SparseBlock[] =>
  eventContent(
    file,
    "Identifier Hints",
    "Named energy-event identifier from the energy summary layer.",
  );

export const machineEventsContent = (file: EventsFile | null): SparseBlock[] =>
  eventContent(file, "Machine Events", "Rule / machine event window.");

export const mlEventsContent = (file: EventsFile | null): SparseBlock[] =>
  eventContent(file, "ML Events", "ML-predicted event window (Story 6.1).");

export function phrasesContent(file: SymbolicPhrasesFile | null): SparseBlock[] {
  return (file?.phrases ?? []).map((p) => ({
    id: p.id,
    start_s: p.start_s,
    end_s: p.end_s,
    label: p.group_id || p.label,
    laneLabel: "Symbolic Phrases",
    caption: `${formatRange(p.start_s, p.end_s)}${
      p.melodic_contour ? ` · ${p.melodic_contour}` : ""
    }`,
    reference: p.id,
    detail: p.register_label ?? "-",
    summary: `Phrase window ${p.label}${
      p.group_id ? ` in ${p.group_id}` : ""
    } from the symbolic layer${p.section_name ? ` (${p.section_name})` : ""}.`,
    raw: p.raw ?? p,
  }));
}

// -- dispatch -------------------------------------------------------------

export interface LaneContentSources {
  humanHints?: HumanHintsFile | null;
  dropProposals?: DropProposalsFile | null;
  sections?: readonly SectionRow[];
  harmonicLayer?: HarmonicLayer | null;
  patterns?: PatternsFile | null;
  identifierHints?: EventsFile | null;
  machineEvents?: EventsFile | null;
  mlEvents?: EventsFile | null;
  symbolicPhrases?: SymbolicPhrasesFile | null;
}

/** the sparse (block) lane ids handled by this module, in registry order */
export const SPARSE_LANE_IDS = [
  "humanHints",
  "dropProposals",
  "sections",
  "chords",
  "patterns",
  "identifierHints",
  "machineEvents",
  "mlEvents",
  "phrases",
] as const;

export type SparseLaneId = (typeof SPARSE_LANE_IDS)[number];

export function buildLaneBlocks(
  laneId: string,
  s: LaneContentSources,
): SparseBlock[] {
  switch (laneId) {
    case "humanHints":
      return humanHintsContent(s.humanHints ?? null);
    case "dropProposals":
      return dropProposalsContent(s.dropProposals ?? null);
    case "sections":
      return sectionsContent(s.sections ?? []);
    case "chords":
      return chordsContent(s.harmonicLayer ?? null);
    case "patterns":
      return patternsContent(s.patterns ?? null);
    case "identifierHints":
      return identifierHintsContent(s.identifierHints ?? null);
    case "machineEvents":
      return machineEventsContent(s.machineEvents ?? null);
    case "mlEvents":
      return mlEventsContent(s.mlEvents ?? null);
    case "phrases":
      return phrasesContent(s.symbolicPhrases ?? null);
    default:
      return [];
  }
}
