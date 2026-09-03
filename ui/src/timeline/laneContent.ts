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
  Allin1File,
  CharacterFile,
  DropProposalsFile,
  VocalTranscriptionFile,
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
   * label differently from one still needing a decision, and by the allin1
   * lanes to grey out rows whose section name the model cannot be trusted on.
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

/**
 * allin1 functional sections — what part of the song this is.
 *
 * The label is the thing the shipped Sections lane has no equivalent of: a
 * returning chorus is named `chorus 2`, so the lane says which parts of the
 * song are the same part. When the exporter has marked the song degenerate
 * (allin1 outside its training distribution) the names are shown with a
 * trailing `?` and a muted tint — the boundary may still be right even where
 * the name is not.
 */
export function allin1SectionsContent(file: Allin1File | null): SparseBlock[] {
  const unnamed = file?.labelling_status === "degenerate";
  return (file?.sections ?? []).map((s) => {
    const bars = s.start_bar != null ? `bars ${s.start_bar}–${s.start_bar + s.bars - 1}` : `${s.bars} bars`;
    const repeat =
      s.occurrence_count > 1
        ? `${s.occurrence} of ${s.occurrence_count} ${s.function} sections`
        : `the only ${s.function}`;
    return {
      id: s.id,
      start_s: s.start_s,
      end_s: s.end_s,
      label: unnamed ? `${s.name} ?` : s.name,
      wideLabel: `${unnamed ? `${s.name} ?` : s.name} · ${bars} · ${s.phrase_count} phrase${
        s.phrase_count === 1 ? "" : "s"
      }`,
      ...(unnamed ? { tintId: "allin1Unnamed" } : {}),
      laneLabel: "allin1 Sections",
      caption: `${formatRange(s.start_s, s.end_s)} · ${bars}`,
      reference: s.id,
      detail: s.same_label_as ? `same label as ${s.same_label_as}` : repeat,
      summary: unnamed
        ? `allin1 called this \`${s.function}\`, but it produced too few distinct labels on this song to be trusted — treat the boundary as the finding and the name as unknown.`
        : `allin1 functional section \`${s.function}\` (${repeat}), ${bars}, built from ${s.phrase_count} 8-bar phrase${
            s.phrase_count === 1 ? "" : "s"
          }.`,
      raw: s.raw,
    };
  });
}

/**
 * allin1 section transitions — where a cue belongs, and what kind of change it
 * is. A transition already matching a hand-placed `drop impact` leads with
 * `✓`; everything else is an open question to audition, exactly like the Drop
 * Proposals lane above it.
 */
export function allin1TransitionsContent(file: Allin1File | null): SparseBlock[] {
  return (file?.transitions ?? []).map((t) => {
    const matched = t.matches_human_impact != null;
    const offset =
      t.essentia_beat_offset_s == null
        ? "no beat grid"
        : `${t.essentia_beat_offset_s > 0 ? "+" : ""}${round(t.essentia_beat_offset_s, 3)}s off beat`;
    return {
      id: t.id,
      start_s: t.start_s,
      end_s: t.end_s,
      // A transition block is one bar wide, which at song-overview zoom is far
      // too narrow for `chorus → inst`. The destination is the half that
      // decides the next look, so the narrow label keeps that and the wide one
      // carries the full pair.
      label: `${matched ? "✓" : "?"} → ${t.to}`,
      wideLabel: `${matched ? "✓" : "?"} ${t.pair} · ${t.kind}${
        t.bar != null ? ` · bar ${t.bar}` : ""
      } · ${offset}`,
      ...(matched ? { tintId: "allin1TransitionsMatched" } : {}),
      laneLabel: "allin1 Transitions",
      caption: `${formatRange(t.start_s, t.end_s)} · ${t.kind}${
        matched ? ` · matches human ${round(t.matches_human_impact, 2)}s` : ""
      }`,
      reference: t.id,
      detail: t.on_downbeat ? "on a downbeat" : "off the downbeat",
      summary: `Section change ${t.pair} at ${round(t.time_s, 2)}s (${offset}${
        t.on_downbeat ? ", on an allin1 downbeat" : ""
      }). ${
        matched
          ? `Within 0.5 s of the hand-placed drop impact at ${round(t.matches_human_impact, 2)}s.`
          : "No hand-placed impact here — audition it: a transition is where a cue belongs whether or not anyone has labelled it."
      }`,
      raw: t.raw,
    };
  });
}

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
 * Vocal transcription — the sung lyric line, with as much timing as the models
 * actually provide.
 *
 * One block per lyric line, across every source in the file: the
 * `whisper-large-v3` baseline and whichever of VocalParse / ACE-Step has been
 * run. Blocks are tinted by source so the baseline reads apart from the models
 * being tried against it, and every block says how its timing was arrived at —
 * `aligned to whisper words`, `approx`, `span` — because neither singing model
 * emits trustworthy per-word seconds and the lane must not imply otherwise.
 *
 * ACE-Step's `[Section]` tags, when present, are appended as wide spans so its
 * form read can be eyeballed against Sections and allin1 Sections beside it.
 */
export function vocalTranscriptionContent(
  file: VocalTranscriptionFile | null,
): SparseBlock[] {
  const out: SparseBlock[] = [];
  for (const source of file?.sources ?? []) {
    const baseline = source.kind === "baseline";
    const short = source.model.replace(/\s*\(.*\)$/, "").split(",")[0] ?? source.model;
    const tintId = baseline ? "vocalTranscriptionBaseline" : "vocalTranscriptionModel";
    const timing = baseline
      ? "word timestamps"
      : source.alignment === "words"
        ? "aligned to whisper words"
        : source.alignment === "native"
          ? "model timestamps"
          : source.alignment === "span"
            ? "whole-span only"
            : "approximate timing";

    for (const line of source.lines) {
      const label = line.text.length > 32 ? `${line.text.slice(0, 31)}…` : line.text || "♪";
      out.push({
        id: `${short}-${line.id}`,
        start_s: line.start_s,
        end_s: line.end_s,
        label,
        wideLabel: `${short}: ${line.text || "♪"}`,
        tintId,
        laneLabel: "Vocal Transcription",
        caption: `${formatRange(line.start_s, line.end_s)} · ${short}${
          line.approx ? " · approx" : ""
        }`,
        reference: line.id,
        detail: short,
        summary: `${short} — "${line.text}"${
          source.language ? ` (${source.language})` : ""
        }. Timing: ${timing}${
          line.approx ? ", approximate — not measured" : ""
        }.${source.alignment_reason ? ` ${source.alignment_reason}.` : ""}`,
        raw: line.raw,
      });
    }

    for (const span of source.structure) {
      out.push({
        id: `${short}-${span.id}`,
        start_s: span.start_s,
        end_s: span.end_s,
        label: span.tag,
        wideLabel: `${span.tag}${span.instruments ? ` · ${span.instruments}` : ""} · ${short}`,
        tintId: "vocalTranscriptionStructure",
        laneLabel: "Vocal Transcription",
        caption: `${formatRange(span.start_s, span.end_s)} · ${short} structure`,
        reference: span.id,
        detail: `${short} structure`,
        summary: `${short} tagged this span \`${span.tag}\`${
          span.instruments ? ` (${span.instruments})` : ""
        } — a form read to compare against Sections and allin1 Sections, derived from the lines it contains.`,
        raw: span as unknown as Record<string, unknown>,
      });
    }
  }
  out.sort((a, b) => a.start_s - b.start_s);
  return out;
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
  allin1?: Allin1File | null;
  character?: CharacterFile | null;
  vocalTranscription?: VocalTranscriptionFile | null;
  identifierHints?: EventsFile | null;
  machineEvents?: EventsFile | null;
  mlEvents?: EventsFile | null;
  symbolicPhrases?: SymbolicPhrasesFile | null;
}

/** the sparse (block) lane ids handled by this module, in registry order */
export const SPARSE_LANE_IDS = [
  "humanHints",
  "dropProposals",
  "allin1Transitions",
  "sections",
  "character",
  "vocalTranscription",
  "allin1Sections",
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
    case "allin1Transitions":
      return allin1TransitionsContent(s.allin1 ?? null);
    case "sections":
      return sectionsContent(s.sections ?? []);
    case "allin1Sections":
      return allin1SectionsContent(s.allin1 ?? null);
    case "character":
      return characterContent(s.character ?? null);
    case "vocalTranscription":
      return vocalTranscriptionContent(s.vocalTranscription ?? null);
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
