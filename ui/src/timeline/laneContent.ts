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

import type {
  EventTimeline,
  HumanHintsFile,
  HarmonicLayer,
  SectionRow,
  SegmentationSection,
} from "../data/types";
import type {
  CharacterFile,
  DropProposalsFile,
  MoisesLyricsFile,
  VocalTranscriptionFile,
  VocalPhrasesFile,
  ReactiveBandsFile,
  GridFile,
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
 * form read can be eyeballed against the Sections lane beside it.
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
        } — a form read to compare against the Sections lane, derived from the lines it contains.`,
        raw: span as unknown as Record<string, unknown>,
      });
    }
  }
  out.sort((a, b) => a.start_s - b.start_s);
  return out;
}

/**
 * Which confidence-tint bucket a Moises token falls in. The `<SOL>` / `<EOL>`
 * line markers carry no confidence and get their own neutral tint; every word
 * is tinted on a green → amber → red ramp by the score Moises reported, so a
 * glance at the lane shows where the transcription is shaky (dense or effected
 * vocals) without reading a single number.
 */
function moisesTintId(kind: string, confidence: number | null): string {
  if (kind !== "word") return "moisesLyricsMarker";
  if (confidence == null) return "moisesLyricsUnscored";
  if (confidence >= 0.7) return "moisesLyricsHigh";
  if (confidence >= 0.4) return "moisesLyricsMid";
  return "moisesLyricsLow";
}

/**
 * Moises lyrics — the external word-level sung-lyric reference, one block per
 * token: every word plus the `<SOL>` / `<EOL>` line markers, ungrouped and in
 * time order. It sits directly under Human Hints so a hand-marked window
 * ("Breath", "Vocal outro") can be checked against exactly which words are
 * being sung when. Blocks are tinted by per-word confidence.
 */
export function moisesLyricsContent(file: MoisesLyricsFile | null): SparseBlock[] {
  return (file?.tokens ?? []).map((t) => {
    const text = t.text || "♪";
    const marker = t.kind !== "word";
    return {
      id: t.id,
      start_s: t.start_s,
      end_s: t.end_s,
      label: text.length > 24 ? `${text.slice(0, 23)}…` : text,
      wideLabel: t.confidence != null ? `${text} · ${round(t.confidence)}` : text,
      tintId: moisesTintId(t.kind, t.confidence),
      laneLabel: "Moises Lyrics",
      caption: `${formatRange(t.start_s, t.end_s)}${
        t.confidence != null ? ` · conf ${round(t.confidence)}` : ""
      }`,
      reference: t.id,
      detail: marker
        ? t.kind === "sol"
          ? "start of line"
          : "end of line"
        : `line ${t.line_id}`,
      summary: marker
        ? `Moises line marker \`${t.text}\` — ${
            t.kind === "sol" ? "start" : "end"
          } of line ${t.line_id}. External reference, read-only.`
        : `Moises sung word "${t.text}" (line ${t.line_id})${
            t.confidence != null
              ? `, transcription confidence ${round(t.confidence)}`
              : ", no confidence reported"
          }. External reference — read-only ground truth, not a pipeline output.`,
      raw: t.raw,
    };
  });
}

/**
 * Top-level Sections lane — the projected `sections.json` rows, each labelled
 * `NNN Function (confidence)` straight from the backend (plan v3.0 item 7).
 * The inspector's functional detail (`function`, `function_confidence`,
 * `function_status`, `same_label_as`) lives only on the artifact-scoped
 * `section_segmentation/sections.json`, so it is joined in here by
 * `section_id` and merged into `raw` for the block inspector to read.
 */
export function sectionsContent(
  rows: readonly SectionRow[],
  segmentation?: readonly SegmentationSection[],
): SparseBlock[] {
  const bySectionId = new Map<string, SegmentationSection>(
    (segmentation ?? []).map((s) => [s.section_id, s]),
  );
  return rows.map((s, i) => {
    const seg = bySectionId.get(s.section_id);
    return {
      id: s.section_id ?? `section-${String(i + 1).padStart(3, "0")}`,
      start_s: s.start,
      end_s: s.end,
      label: s.label,
      laneLabel: "Sections",
      caption: `${formatRange(s.start, s.end)}${
        s.confidence != null ? ` · conf ${round(s.confidence)}` : ""
      }`,
      reference: s.section_id ?? "-",
      detail: seg?.same_label_as
        ? `same label as ${seg.same_label_as}`
        : (seg?.function_status ?? "-"),
      summary:
        s.description ||
        "Section navigation stays browser-local and moves only the shared playback cursor.",
      raw: seg
        ? {
            ...s,
            function: seg.function,
            function_confidence: seg.function_confidence,
            function_status: seg.function_status,
            same_label_as: seg.same_label_as,
          }
        : s,
    };
  });
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


/**
 * Vocal phrase / instrumental gap / sustained-note blocks from
 * `experiments/vocal_phrases` (Part A — no model, local-auto-gain hysteresis
 * over the vocal stem). A proposal to audition against Human Hints and
 * Moises Lyrics directly above it, per constitution §3.2.
 */
export function vocalPhrasesContent(file: VocalPhrasesFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const kindLabel =
      b.kind === "vocal_phrase" ? "phrase" : b.kind === "instrumental_gap" ? "gap" : "sustained";
    return {
      id: `vocal-phrase-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: b.kind === "sustained_note" ? `♪ ${kindLabel}` : kindLabel,
      ...(b.kind === "instrumental_gap" ? { tintId: "vocalPhrasesGap" } : {}),
      ...(b.kind === "sustained_note" ? { tintId: "vocalPhrasesSustained" } : {}),
      wideLabel: `${kindLabel} · conf ${round(b.confidence, 2)}${b.note_hz ? ` · ${Math.round(b.note_hz)}Hz` : ""}`,
      laneLabel: "Vocal Phrases",
      caption: `${formatRange(b.start_s, b.end_s)} · conf ${round(b.confidence, 2)}`,
      reference: `vocal-phrase-${i + 1}`,
      detail: kindLabel,
      summary: `experiments/vocal_phrases (Part A, no model) — a ${
        b.kind === "vocal_phrase" ? "detected sung phrase" : b.kind === "instrumental_gap" ? "gap with no vocal activity" : "sustained held note"
      } over the vocal stem's local-auto-gain envelope.`,
      raw: b,
    };
  });
}

/**
 * Discrete accents from `experiments/reactive_bands` — locally auto-gained
 * band-power spikes, budget-matched and threshold-calibrated (see the
 * experiment's README, which reports the local-normalisation ablation coming
 * back *against* the headline hypothesis once measured fairly). The dense
 * per-beat bass/mid/treb stream this experiment also produces is not
 * rendered here — see the README.
 */
export function reactiveBandsContent(file: ReactiveBandsFile | null): SparseBlock[] {
  return (file?.accents ?? []).map((a, i) => ({
    id: `reactive-accent-${i + 1}`,
    start_s: a.time_s,
    end_s: a.time_s + 0.05,
    label: `${a.band} ${round(a.strength, 1)}`,
    laneLabel: "Reactive Bands",
    caption: `${formatRange(a.time_s, a.time_s)} · ${a.band} band, strength ${round(a.strength, 2)}${
      a.bar != null ? ` · bar ${a.bar} beat ${a.beat}` : ""
    }`,
    reference: `reactive-accent-${i + 1}`,
    detail: a.band,
    summary: `experiments/reactive_bands — an instantaneous ${a.band}-band power spike above its own damped (locally auto-gained) twin.`,
    raw: a,
  }));
}

/**
 * Named gesture phases (approach/build/tension/impact/release) and
 * section-pair transitions ("<from> → <to>") from `song_event_timeline.json`
 * -- the production `gestures` stage (plan v3.0 item 9, replacing the
 * Machine Events / Identifier Hints lanes it superseded). Never claims a
 * "drop" by name (constitution §5.2); each row is already flat, so one block
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
 * Phrase-grid boundaries from `experiments/grid_consensus` — the resolved
 * downbeat phase's derived 8/16-bar phrase edges. `status: "unknown"` marks
 * a song where trackers disagreed and musical evidence did not resolve it
 * (constitution §7 — say so rather than snapping); those blocks are tinted
 * distinctly as disputed.
 */
export function gridPhraseContent(file: GridFile | null): SparseBlock[] {
  const disputed = file?.status === "unknown";
  return (file?.boundaries ?? []).map((b, i) => ({
    id: `phrase-grid-${i + 1}`,
    start_s: b.time_s,
    end_s: b.time_s + 0.1,
    label: `bar ${b.bar}`,
    ...(disputed ? { tintId: "gridDisputed" } : {}),
    wideLabel: `phrase boundary · bar ${b.bar} · conf ${round(b.confidence, 2)}${disputed ? " · DISPUTED" : ""}`,
    laneLabel: "Phrase Grid",
    caption: `${formatRange(b.time_s, b.time_s)} · bar ${b.bar}${disputed ? " · disputed grid" : ""}`,
    reference: `phrase-grid-${i + 1}`,
    detail: disputed ? "grid status: unknown" : "grid status: resolved",
    summary: `experiments/grid_consensus — an ${file?.phrase_length_bars ?? "?"}-bar phrase boundary at bar ${b.bar}${
      disputed ? "; this song's downbeat phase was not confidently resolved (trackers disagreed, evidence inconclusive) — treat the whole grid on this song with caution" : ""
    }.`,
    raw: b,
  }));
}

// -- dispatch -------------------------------------------------------------

export interface LaneContentSources {
  humanHints?: HumanHintsFile | null;
  moisesLyrics?: MoisesLyricsFile | null;
  dropProposals?: DropProposalsFile | null;
  sections?: readonly SectionRow[];
  sectionSegmentation?: readonly SegmentationSection[];
  harmonicLayer?: HarmonicLayer | null;
  character?: CharacterFile | null;
  vocalTranscription?: VocalTranscriptionFile | null;
  vocalPhrases?: VocalPhrasesFile | null;
  reactiveBands?: ReactiveBandsFile | null;
  gestures?: EventTimeline | null;
  grid?: GridFile | null;
}

/** the sparse (block) lane ids handled by this module, in registry order */
export const SPARSE_LANE_IDS = [
  "humanHints",
  "moisesLyrics",
  "dropProposals",
  "vocalPhrases",
  "reactiveBands",
  "gestures",
  "gridPhrase",
  "sections",
  "character",
  "vocalTranscription",
  "chords",
] as const;

export type SparseLaneId = (typeof SPARSE_LANE_IDS)[number];

export function buildLaneBlocks(
  laneId: string,
  s: LaneContentSources,
): SparseBlock[] {
  switch (laneId) {
    case "humanHints":
      return humanHintsContent(s.humanHints ?? null);
    case "moisesLyrics":
      return moisesLyricsContent(s.moisesLyrics ?? null);
    case "dropProposals":
      return dropProposalsContent(s.dropProposals ?? null);
    case "vocalPhrases":
      return vocalPhrasesContent(s.vocalPhrases ?? null);
    case "reactiveBands":
      return reactiveBandsContent(s.reactiveBands ?? null);
    case "gestures":
      return gesturesContent(s.gestures ?? null);
    case "gridPhrase":
      return gridPhraseContent(s.grid ?? null);
    case "sections":
      return sectionsContent(s.sections ?? [], s.sectionSegmentation ?? []);
    case "character":
      return characterContent(s.character ?? null);
    case "vocalTranscription":
      return vocalTranscriptionContent(s.vocalTranscription ?? null);
    case "chords":
      return chordsContent(s.harmonicLayer ?? null);
    default:
      return [];
  }
}
