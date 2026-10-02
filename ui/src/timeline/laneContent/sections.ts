// sections.ts — Human/Moises/allin1 Sections, the fused Sections lane, the
// allin1 Posterior and Stem Presence Sections candidates and Arrangement State. Split out of laneContent.ts (v3.9 item 7) with no
// behaviour change; see laneContent.ts for the dispatch table and shared
// SparseBlock type.

import type {
  HumanSegmentsFile,
  MoisesSegmentsFile,
  SectionRow,
  SegmentationSection,
} from "../../data/types";
import type {
  Allin1PosteriorFile,
  ArrangementStateFile,
  StemPresenceSectionsFile,
  SectionNamesFile,
} from "../../data/sparseArtifacts";
import type { SparseBlock } from "../laneContent";
import { formatRange, round } from "./shared";

/**
 * Human Sections — the operator's hand-authored segmentation
 * (reference/human/segments.json). `label` is a fixed value, optional (one
 * of SEGMENT_FUNCTION_NAMES, never free text) — when set it's the block's
 * identity and doubles as the block label, falling back to the synthesized
 * id when unset; `description` is optional free text, surfaced as the block
 * summary when present. The block id is synthesized from array position.
 */
export function humanSectionsContent(file: HumanSegmentsFile | null): SparseBlock[] {
  return (file ?? []).map((s, i) => {
    const id = `segment-${String(i + 1).padStart(3, "0")}`;
    return {
      id,
      start_s: s.start,
      end_s: s.end,
      label: s.label || id,
      laneLabel: "Human Sections",
      caption: formatRange(s.start, s.end),
      reference: id,
      detail: "-",
      summary: s.description?.trim() || "Hand-authored section segmentation.",
      raw: s,
    };
  });
}

/**
 * Moises Sections — Moises.ai's reference segmentation
 * (reference/moises/segments.json). Same bare-array shape as Human Sections
 * but read-only and carries no confidence field of its own — see
 * docs/reference/analysis.segments.md for the fusion precedence this lane
 * exists to let the operator audit visually.
 */
export function moisesSectionsContent(file: MoisesSegmentsFile | null): SparseBlock[] {
  return (file ?? []).map((s, i) => {
    const id = `moises-segment-${String(i + 1).padStart(3, "0")}`;
    return {
      id,
      start_s: s.start,
      end_s: s.end,
      label: s.label || id,
      laneLabel: "Moises Sections",
      caption: formatRange(s.start, s.end),
      reference: id,
      detail: "-",
      summary: s.description?.trim() || "Moises.ai reference segmentation.",
      raw: s,
    };
  });
}

/**
 * allin1 Segmentation — the raw, pre-fusion analyzer output
 * (artifacts/section_segmentation/sections.json), before any
 * reference/human or reference/moises override is applied to the published
 * `sections.json`. Exists so the operator can compare all three sources
 * (Human Sections, Moises Sections, this lane) against the fused Sections
 * lane at a glance — see docs/reference/analysis.segments.md.
 */
export function allin1SectionsContent(
  sections: readonly SegmentationSection[],
): SparseBlock[] {
  return sections.map((s, i) => ({
    id: s.section_id ?? `allin1-section-${String(i + 1).padStart(3, "0")}`,
    start_s: s.start,
    end_s: s.end,
    label: s.function || "-",
    laneLabel: "allin1 Segmentation",
    caption: `${formatRange(s.start, s.end)}${
      s.confidence != null ? ` · conf ${round(s.confidence)}` : ""
    }`,
    reference: s.section_id ?? "-",
    detail: s.same_label_as
      ? `same label as ${s.same_label_as}`
      : (s.function_status ?? "-"),
    summary: "Our own segmentation (allin1), before any human/moises override.",
    raw: s,
  }));
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
    const functionStatus = seg?.function_status ?? s.function_status;
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
      raw: {
        ...s,
        ...(seg
          ? {
              function: seg.function,
              function_confidence: seg.function_confidence,
              same_label_as: seg.same_label_as,
            }
          : {}),
        function_status: functionStatus,
      },
    };
  });
}

/**
 * Shadow-label spans from `experiments/allin1_posterior` — a non-argmax
 * allin1 frame-posterior label sustaining a share the published 8-bar argmax
 * discards. Not ground truth, and per docs/experiments.md loses to an
 * even-grid baseline on boundary recall on 3/4 gold songs — a proposal to
 * audition against Sections, sitting below it.
 */
export function allin1PosteriorContent(file: Allin1PosteriorFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => ({
    id: `allin1-posterior-${i + 1}`,
    start_s: b.start_s,
    end_s: b.end_s,
    label: b.label,
    wideLabel: `${b.label} · share ${round(b.mean_share, 2)}`,
    laneLabel: "allin1 Posterior",
    caption: `${formatRange(b.start_s, b.end_s)} · ${b.label} · share ${round(b.mean_share, 2)}`,
    reference: `allin1-posterior-${i + 1}`,
    detail: b.label,
    summary: `experiments/allin1_posterior — a non-argmax allin1 label ("${b.label}") sustaining ${round(b.mean_share, 2)} of the frame posterior; ${round(b.published_overlap, 2)} overlap with the published section at that time.`,
    raw: b,
  }));
}

/**
 * Bass/drums-presence state-machine sections from
 * `experiments/stem_presence_sections` — coarse state (full / bass_only /
 * drums_only / stripped), hysteresis-merged so a short mid-section dip does
 * not split it, boundaries moved to the nearest physical stem onset.
 * `vocals_present_fraction` is annotation only — vocals never cut a
 * boundary. A proposal to audition against Human Hints, never ground truth;
 * not yet scored corpus-wide.
 */
export function stemPresenceSectionsContent(
  file: StemPresenceSectionsFile | null,
): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => ({
    id: `stem-presence-sections-${i + 1}`,
    start_s: b.start_s,
    end_s: b.end_s,
    label: b.state,
    wideLabel: `${b.state} · drums ${b.drums_detail} · vocals ${round(b.vocals_present_fraction, 2)}`,
    laneLabel: "Stem Presence Sections",
    caption: `${formatRange(b.start_s, b.end_s)} · bars ${b.bar_start}-${b.bar_end} · ${b.state}`,
    reference: `stem-presence-sections-${i + 1}`,
    detail: b.state,
    summary: `experiments/stem_presence_sections — ${b.state} (drums ${b.drums_detail}), ` +
      `vocals present ${round(b.vocals_present_fraction, 2)} of bars, ` +
      `confidence ${b.confidence == null ? "no confidence reported" : round(b.confidence, 3)}, ` +
      `boundary ${b.boundary_resolved == null ? "initial state" : b.boundary_resolved ? "resolved to a physical onset" : "no onset found — left at the bar edge"}.`,
    raw: b,
  }));
}

/**
 * Who-is-playing state-change blocks from the top-level published
 * `arrangement_state.json` (the `detect-arrangement-state` stage — no audio,
 * no model, derived from the published per-stem RMS series). Auditioned
 * against Human Hints directly above it (this lane sits below Moises Lyrics,
 * above Drop Proposals).
 *
 * `label` is kept short for a narrow block: the change itself when there is
 * one (`+drums`, `-bass -vocals`, space-joined tokens for multiple stems), or
 * initials of the stems currently playing (`b+d+h+v`) for the leading block,
 * which has no prior state to diff against.
 */
export function arrangementStateContent(file: ArrangementStateFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const changeTokens = [
      ...b.entered.map((s) => `+${s}`),
      ...b.left.map((s) => `-${s}`),
    ];
    const isInitial = b.entered.length === 0 && b.left.length === 0;
    const label = changeTokens.length > 0
      ? changeTokens.join(" ")
      : isInitial
        ? b.playing.map((s) => s[0]).join("+") || "silence"
        : "no change";
    const marginClause = b.margin_db != null ? ` · margin ${round(b.margin_db, 1)}dB` : "";
    const playingList = b.playing.length > 0 ? b.playing.join(", ") : "nothing";
    const changeSummary = changeTokens.length > 0
      ? `${changeTokens.join(" ")} at this block's start.`
      : isInitial
        ? "the leading span, before the first detected change."
        : "no change at this block's start.";
    return {
      id: `arrangement-state-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label,
      ...(b.playing.length <= 1 ? { tintId: "arrangementStateSparse" } : {}),
      wideLabel: `${changeTokens.length > 0 ? `${changeTokens.join(" ")} · ` : ""}${playingList}${marginClause}`,
      laneLabel: "Arrangement State",
      caption: `${formatRange(b.start_s, b.end_s)} · playing: ${playingList}${
        b.margin_db != null ? marginClause : " · initial state"
      }`,
      reference: `arrangement-state-${i + 1}`,
      detail: `playing: ${playingList}`,
      summary: `arrangement_state.json — who is playing over this span, derived from the published per-stem RMS (no model). ${changeSummary}`,
      raw: b,
    };
  });
}

/**
 * Section Names from `experiments/section_names` — every phrase named in the
 * typical EDM sequence (`docs/segments-vocabulary.md`), boundaries on the
 * phrase edges (a Fill / Pre-Drop / Build-Up start may sit on its own evidence
 * time: `start_kind` says which). A song with no build->drop unit keeps its
 * current `sections.json` labels, tinted grey and attributed. Confidence is a
 * heuristic score, never a calibrated probability; `null` is printed as such.
 * A proposal to audition against Human Sections, not ground truth.
 */
export function sectionNamesContent(file: SectionNamesFile | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => {
    const kept = b.source !== "section_names";
    const conf = b.confidence == null ? "no confidence reported" : `confidence ${round(b.confidence, 2)}`;
    const start =
      b.start_kind === "phrase_edge" ? "starts on a phrase edge"
      : b.start_kind === "song_start" ? "starts at the song start"
      : b.start_kind === "kept_current" ? "boundary kept from sections.json"
      : b.start_kind === "evidence" ? "starts at its own evidence time (snapped to a trusted beat)"
      : "starts at its own evidence time (not snapped: no trusted beat near)";
    return {
      id: `sectionNames-${i + 1}`,
      start_s: b.start_s,
      end_s: b.end_s,
      label: b.label,
      wideLabel: b.confidence == null ? b.label : `${b.label} · ${round(b.confidence, 2)}`,
      laneLabel: "Section Names",
      caption: `${formatRange(b.start_s, b.end_s)} · ${b.label}${kept ? " (kept current label)" : ""}`,
      reference: `sectionNames-${i + 1}`,
      detail: b.label,
      summary:
        `experiments/section_names — ${b.label}; ${conf}; ${start}; ` +
        `source ${b.source}${b.unit ? `, ${b.unit}` : ""}${b.phrase_ids.length ? `, phrases ${b.phrase_ids.join(", ")}` : ""}` +
        `${b.inherited_from ? `; label inherited from ${b.inherited_from}` : ""}. Why: ${b.why.join("; ")}.`,
      tintId: kept ? "sectionNamesKept" : "sectionNames",
      raw: b,
    };
  });
}
