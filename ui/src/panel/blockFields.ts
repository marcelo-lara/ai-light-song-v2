// blockFields.ts — the read-only block-inspector field map.
//
// Ported from the previous app's src/lib/timeline/sparseContent.js (`buildSparseLaneContent`)
// + the previous app's src/components/SelectionDetailCard/selectionFields.js
// (`buildSelectionFields`). `blockFields(laneId, selection)` returns the ordered
// <dl> rows the right-panel inspector renders; `selectionFrom*` normalise a
// clicked segment / lane marker into the shared `BlockSelection` payload.

import type { SectionRow } from "../data/types";
import type { LaneMarker } from "../timeline/laneRenderers";
import type { SegmentBlock } from "../timeline/segments";

export interface Field {
  label: string;
  value: string;
}

export interface BlockSelection {
  laneId: string;
  laneLabel: string;
  /** heading */
  label: string;
  start_s: number;
  end_s: number | null;
  confidence?: number | null;
  reference?: string | null;
  detail?: string | null;
  section_id?: string | null;
  created_by?: string | null;
  caption?: string | null;
  summary?: string | null;
  /** full source object — dumped by the "show raw" disclosure */
  raw: unknown;
}

export const LANE_LABELS: Record<string, string> = {
  segments: "Segments",
  sections: "Sections",
  dropProposals: "Drop Proposals",
  allin1Sections: "allin1 Sections",
  allin1Transitions: "allin1 Transitions",
  character: "Character",
  vocalTranscription: "Vocal Transcription",
  humanHints: "Human Hints",
  moisesLyrics: "Moises Lyrics",
  chords: "Chord Regions",
  drums: "Drum Density",
  energy: "Energy Profile",
  validation: "Regression Overlay",
};

// ---------------------------------------------------------------------------
// formatting (ported from the previous app's src/lib/utils.js)
// ---------------------------------------------------------------------------

export function formatDuration(seconds: number | null | undefined): string {
  const n = Number(seconds);
  if (!Number.isFinite(n)) return "-";
  const m = Math.floor(n / 60);
  const rem = n - m * 60;
  return `${m}:${rem.toFixed(1).padStart(4, "0")}`;
}

export function formatRange(
  start: number | null | undefined,
  end: number | null | undefined,
): string {
  if (end == null) return formatDuration(start);
  return `${formatDuration(start)}–${formatDuration(end)}`;
}

export function roundNumber(value: unknown, digits = 2): string {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "-";
}

// ---------------------------------------------------------------------------
// raw-record readers
// ---------------------------------------------------------------------------

function rec(raw: unknown): Record<string, unknown> {
  return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
}
function str(v: unknown): string | null {
  if (v == null) return null;
  if (typeof v === "string") return v.trim() || null;
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  return null;
}
function firstStr(...vs: unknown[]): string | null {
  for (const v of vs) {
    const s = str(v);
    if (s) return s;
  }
  return null;
}
function summaryOf(r: Record<string, unknown>): string | null {
  const nested = (key: string): string | null => {
    const obj = r[key];
    return obj && typeof obj === "object"
      ? str((obj as Record<string, unknown>).summary)
      : null;
  };
  const notes = r.notes;
  return firstStr(
    r.summary,
    r.description,
    nested("explanation"),
    nested("saliency"),
    nested("evidence"),
    Array.isArray(notes) ? notes.join(" ") : notes,
  );
}

// ---------------------------------------------------------------------------
// blockFields — the per-lane <dl> row map
// ---------------------------------------------------------------------------

/**
 * Ordered inspector rows for a clicked block. `laneId` selects the
 * lane-specific extras; the shared rows (lane, window, confidence, reference,
 * section, created-by, context) always come first in `buildSelectionFields`
 * order.
 */
export function blockFields(laneId: string, sel: BlockSelection): Field[] {
  const r = rec(sel.raw);
  const out: Array<Field | null> = [
    { label: "Lane", value: sel.laneLabel || LANE_LABELS[laneId] || laneId },
    { label: "Window", value: formatRange(sel.start_s, sel.end_s) },
    sel.confidence != null && Number.isFinite(Number(sel.confidence))
      ? { label: "Confidence", value: roundNumber(sel.confidence, 2) }
      : null,
    sel.reference && sel.reference !== "-"
      ? { label: "Reference", value: sel.reference }
      : null,
    sel.detail && sel.detail !== "-" && sel.detail !== sel.reference
      ? { label: "Detail", value: sel.detail }
      : null,
    sel.section_id ? { label: "Section", value: sel.section_id } : null,
    sel.created_by ? { label: "Created by", value: sel.created_by } : null,
  ];

  switch (laneId) {
    case "segments":
    case "sections": {
      // v3.0 item 7: the allin1 functional-segmentation detail, joined onto
      // the block's raw payload by `section_id` from
      // `artifacts/section_segmentation/sections.json`. Field labels are the
      // artifact's own field names, not a friendlified label (plan V7.3).
      const fn = str(r.function);
      if (fn) out.push({ label: "function", value: fn });
      const fnConf = r.function_confidence;
      if (fnConf != null && Number.isFinite(Number(fnConf)))
        out.push({ label: "function_confidence", value: roundNumber(fnConf, 2) });
      const fnStatus = str(r.function_status);
      if (fnStatus) out.push({ label: "function_status", value: fnStatus });
      // Always shown, even for a section's first occurrence (r.same_label_as
      // is null there) — plan v3.0 item 7 V7.3 requires the field name to be
      // visible on the first Sections block, not only on a repeat.
      const sameAs = str(r.same_label_as);
      out.push({ label: "same_label_as", value: sameAs || "null" });
      break;
    }
    case "allin1Sections": {
      const bar = str(r.start_bar);
      const bars = str(r.bars);
      if (bar && bars) out.push({ label: "Bars", value: `${bar} +${bars}` });
      const phrases = str(r.phrase_count);
      if (phrases) out.push({ label: "8-bar phrases", value: phrases });
      const same = str(r.same_label_as);
      if (same) out.push({ label: "Same label as", value: same });
      const status = str(r.function_status);
      if (status) out.push({ label: "Function", value: status });
      break;
    }
    case "character": {
      const kind = str(r.kind);
      if (kind) out.push({ label: "Kind", value: kind });
      const source = str(r.source);
      if (source) out.push({ label: "Sources agreeing", value: source });
      const ev = rec(r.evidence);
      for (const [key, value] of Object.entries(ev)) {
        const n = Number(value);
        if (Number.isFinite(n))
          out.push({ label: key.replace(/_/g, " "), value: roundNumber(n, 3) });
      }
      break;
    }
    case "moisesLyrics": {
      const text = str(r.text);
      if (text) out.push({ label: "Token", value: text });
      const lineId = str(r.line_id);
      if (lineId) out.push({ label: "Line", value: lineId });
      const conf = r.confidence;
      if (conf != null && Number.isFinite(Number(conf)))
        out.push({ label: "Confidence", value: roundNumber(Number(conf), 2) });
      break;
    }
    case "vocalTranscription": {
      const text = str(r.text);
      if (text) out.push({ label: "Text", value: text });
      if (r.approx === true)
        out.push({ label: "Timing", value: "approximate — not measured" });
      const conf = r.confidence;
      if (conf != null && Number.isFinite(Number(conf)))
        out.push({ label: "Confidence", value: roundNumber(Number(conf), 3) });
      const tag = str(r.tag);
      if (tag) out.push({ label: "Structure tag", value: tag });
      const instr = str(r.instruments);
      if (instr) out.push({ label: "Instruments", value: instr });
      break;
    }
    case "allin1Transitions": {
      const pair = str(r.pair);
      if (pair) out.push({ label: "Label pair", value: pair });
      const kind = str(r.kind);
      if (kind) out.push({ label: "Kind", value: kind });
      const offset = r.essentia_beat_offset_s;
      if (offset != null)
        out.push({ label: "Offset to essentia beat", value: `${roundNumber(offset, 3)} s` });
      out.push({ label: "On downbeat", value: r.on_downbeat === true ? "yes" : "no" });
      const match = r.matches_human_impact;
      if (match != null)
        out.push({ label: "Matches human impact", value: `${roundNumber(match, 2)} s` });
      break;
    }
    case "chords": {
      const roman = str(r.roman);
      if (roman) out.push({ label: "Roman", value: roman });
      const name = firstStr(r.name, r.label);
      if (name) out.push({ label: "Chord", value: name });
      break;
    }
    case "drums": {
      const t = str(r.event_type);
      if (t) out.push({ label: "Event type", value: t });
      break;
    }
    case "energy": {
      const intensity = firstStr(r.intensity, r.value);
      if (intensity)
        out.push({ label: "Intensity", value: roundNumber(intensity, 2) });
      const kind = str(r.kind);
      if (kind) out.push({ label: "Kind", value: kind });
      break;
    }
    default:
      break;
  }

  if (sel.caption) out.push({ label: "Context", value: sel.caption });
  return out.filter((f): f is Field => f != null);
}

// ---------------------------------------------------------------------------
// normalisers — clicked segment / lane marker -> BlockSelection
// ---------------------------------------------------------------------------

/** "003 Momentum Lift (0.80)" -> "Momentum Lift" */
function cleanLabel(label: string): string {
  return (
    label
      .replace(/^\s*\d+\s+/, "")
      .replace(/\s*\([0-9]*\.?[0-9]+\)\s*$/, "")
      .trim() || label.trim()
  );
}

export function selectionFromSection(
  block: Pick<SegmentBlock, "section">,
  laneId: "segments" | "sections" = "segments",
): BlockSelection {
  const s: SectionRow = block.section;
  return {
    laneId,
    laneLabel: LANE_LABELS[laneId]!,
    label: cleanLabel(s.label),
    start_s: s.start,
    end_s: s.end,
    confidence: s.confidence,
    reference: s.section_id,
    detail: null,
    section_id: s.section_id,
    created_by: null,
    caption: `${formatRange(s.start, s.end)}${
      s.confidence != null ? ` · conf ${roundNumber(s.confidence, 2)}` : ""
    }`,
    summary:
      s.description ||
      "Section navigation stays browser-local and moves only the shared playback cursor.",
    raw: s,
  };
}

export function selectionFromMarker(marker: LaneMarker): BlockSelection {
  const r = rec(marker.raw);
  const laneId = marker.laneId;
  const start = Number(
    firstStr(r.start_s, r.start_time, r.start, r.time, marker.time) ??
      marker.time,
  );
  const endRaw = firstStr(r.end_s, r.end_time, r.end);
  const end = endRaw != null ? Number(endRaw) : null;
  const label =
    firstStr(r.label, r.name, r.title, r.id, marker.kind) ?? marker.kind;
  const confidence = firstStr(r.confidence);
  return {
    laneId,
    laneLabel: LANE_LABELS[laneId] ?? laneId,
    label,
    start_s: Number.isFinite(start) ? start : marker.time,
    end_s: end != null && Number.isFinite(end) ? end : null,
    confidence: confidence != null ? Number(confidence) : null,
    reference: firstStr(r.reference, r.pattern_id, r.id, marker.id),
    detail: firstStr(r.section_id, r.created_by, r.model_name),
    section_id: str(r.section_id),
    created_by: firstStr(r.created_by, r.model_name),
    caption:
      (end != null && Number.isFinite(end)
        ? formatRange(start, end)
        : formatDuration(start)) +
      (confidence != null ? ` · conf ${roundNumber(confidence, 2)}` : ""),
    summary: summaryOf(r) ?? `${marker.kind} marker from the ${laneId} lane.`,
    raw: marker.raw ?? marker,
  };
}
