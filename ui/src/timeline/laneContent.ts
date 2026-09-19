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
  HumanSegmentsFile,
  HumanSegmentsSeedFile,
  MoisesSegmentsFile,
  HarmonicLayer,
  SectionRow,
  SegmentationSection,
} from "../data/types";
import type {
  CharacterFile,
  MoisesLyricsFile,
  VocalTranscriptionFile,
  VocalPhrasesFile,
  ArrangementStateFile,
  RhythmDrumIoiFile,
  RhythmStemAutocorrFile,
  RhythmVocalOnsetsFile,
  EnergyLevelFile,
  TensionShapeFile,
  WhisperxVadFile,
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
  /**
   * v3.4 item 5 — the Moises lyric-token id this block represents, when the
   * block is a validatable **word** token (not a `<SOL>`/`<EOL>` marker). The
   * Moises Lyrics events panel renders a ✔ validation button only for a block
   * carrying both this and `lyricValidatable: true`.
   */
  lyricTokenId?: number;
  lyricValidatable?: boolean;
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
    // The lane's own "humanHints" amber tint applies for a "hint" (or absent)
    // type; a "review" hint gets a distinct tint, and a "vocal" hint (a voice
    // sounds continuously across the span) gets its own, so each reads apart
    // on the timeline.
    ...(h.type === "review" ? { tintId: "humanHintsReview" } : {}),
    ...(h.type === "vocal" ? { tintId: "humanHintsVocal" } : {}),
    raw: h,
  }));
}

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
    const tags = [
      s.energy != null ? `E${s.energy}` : null,
      s.tension != null ? `T${s.tension}` : null,
    ].filter((t): t is string => Boolean(t));
    return {
      id,
      start_s: s.start,
      end_s: s.end,
      label: s.label || id,
      laneLabel: "Human Sections",
      caption: tags.length
        ? `${formatRange(s.start, s.end)} · ${tags.join(" ")}`
        : formatRange(s.start, s.end),
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
function moisesTintId(
  kind: string,
  confidence: number | null,
  validated: boolean,
): string {
  if (kind !== "word") return "moisesLyricsMarker";
  // v3.4 item 5 — a hand-verified token reads as validated at a glance, never
  // as one of Moises' own confidence buckets (in particular not the `≥ 0.7`
  // "High" bucket alongside Moises' 0.99s).
  if (validated) return "moisesLyricsValidated";
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
 *
 * v3.4 item 5 — `validatedIds` is the read-time overlay from
 * `reference/human/lyric_validations.json`: a word token whose id is listed is
 * shown at confidence `1` (a value Moises never emits) with the distinct
 * `moisesLyricsValidated` tint. The source file is untouched. Word tokens
 * carry `lyricTokenId` + `lyricValidatable: true` so the events panel can draw
 * a ✔ button for them; markers get neither.
 */
export function moisesLyricsContent(
  file: MoisesLyricsFile | null,
  validatedIds?: ReadonlySet<number> | null,
): SparseBlock[] {
  return (file?.tokens ?? []).map((t) => {
    const text = t.text || "♪";
    const marker = t.kind !== "word";
    const tokenId = Number(t.id);
    const hasId = Number.isInteger(tokenId) && Number.isFinite(tokenId);
    const validated = !marker && hasId && !!validatedIds?.has(tokenId);
    const shownConf = validated ? 1 : t.confidence;
    return {
      id: t.id,
      start_s: t.start_s,
      end_s: t.end_s,
      label: text.length > 24 ? `${text.slice(0, 23)}…` : text,
      wideLabel:
        shownConf != null
          ? `${text} · ${round(shownConf)}${validated ? " · validated" : ""}`
          : text,
      tintId: moisesTintId(t.kind, t.confidence, validated),
      ...(marker || !hasId
        ? {}
        : { lyricTokenId: tokenId, lyricValidatable: true }),
      laneLabel: "Moises Lyrics",
      caption: `${formatRange(t.start_s, t.end_s)}${
        shownConf != null ? ` · conf ${round(shownConf)}` : ""
      }${validated ? " · human-validated" : ""}`,
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
        : validated
          ? `Moises sung word "${t.text}" (line ${t.line_id}) — timing hand-verified by the operator, shown at confidence 1. Overlay from reference/human/lyric_validations.json; reference/moises/lyrics.json is untouched.`
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
    // v3.4 item 3 — the phase-3 energy contest flags (never flips) a `chorus`
    // that is quieter/thinner than the following section. The flag lands on the
    // top-level row's `function_status`, so it wins over the artifact's value.
    const contested = s.function_status === "contested";
    const functionStatus = contested
      ? "contested"
      : (seg?.function_status ?? s.function_status);
    return {
      id: s.section_id ?? `section-${String(i + 1).padStart(3, "0")}`,
      start_s: s.start,
      end_s: s.end,
      label: s.label,
      ...(contested ? { tintId: "sectionsContested" } : {}),
      laneLabel: "Sections",
      caption: `${formatRange(s.start, s.end)}${
        s.confidence != null ? ` · conf ${round(s.confidence)}` : ""
      }${contested ? ` · contested (${s.contested_by ?? "energy"})` : ""}`,
      reference: s.section_id ?? "-",
      detail: contested
        ? `function_status: contested · contested_by: ${s.contested_by ?? "energy"}`
        : seg?.same_label_as
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
        ...(contested ? { contested_by: s.contested_by ?? "energy" } : {}),
      },
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

export function chordsInferenceContent(harmonic: HarmonicLayer | null): SparseBlock[] {
  const key = harmonic?.global_key?.label ?? null;
  const probs = harmonic?.chord_probabilities ?? [];
  return probs.map((c, i) => {
    const nextTime = probs[i + 1]?.time;
    const end_s =
      nextTime != null && nextTime > c.time
        ? nextTime
        : c.time + 0.08;
    const roman = romanNumeral(c.label, key);
    return {
      id: `chords-inference-${String(i + 1).padStart(3, "0")}`,
      start_s: c.time,
      end_s,
      label: c.label || "-",
      ...(roman ? { wideLabel: `${c.label} · ${roman}` } : {}),
      laneLabel: "Chords",
      caption: `${formatRange(c.time, end_s)}${
        c.confidence != null ? ` · conf ${round(c.confidence)}` : ""
      }`,
      reference: roman ?? "-",
      detail: c.beat != null ? `beat ${c.beat}` : "-",
      summary: `Per-beat chord inference ${c.label}${roman ? ` (${roman} in ${key})` : ""} from layer_a_harmonic.chord_probabilities.`,
      raw: {
        ...c,
        roman,
        name: c.label,
      },
    };
  });
}


/**
 * Vocal phrase / instrumental gap / sustained-note blocks from
 * `experiments/vocal_phrases` (Part A — no model, local-auto-gain hysteresis
 * over the vocal stem). A proposal to audition against Human Hints and
 * Moises Lyrics directly above it: experiment proposals sit under the
 * hand-authored truth they are auditioned against.
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
 * `reference/human/segments.seed.json` — `experiments/segment_seeds`' rule-based
 * first-pass draft of energy/tension/rhythm over the operator's segment spans.
 * Unreviewed inference, not operator input; renders every row regardless of
 * whether it has since been reviewed into segments.json. Never invents a value
 * for a missing field — prints the gap instead.
 */
export function segmentSeedsContent(file: HumanSegmentsSeedFile | null): SparseBlock[] {
  return (file ?? []).map((row, i) => {
    const id = `segment-seed-${String(i + 1).padStart(3, "0")}`;
    const tags = [
      row.energy != null ? `E${row.energy}` : null,
      row.tension != null ? `T${row.tension}` : null,
    ].filter((t): t is string => t != null);
    const caption = tags.length
      ? `${formatRange(row.start, row.end)} · ${tags.join(" ")}`
      : formatRange(row.start, row.end);
    const rhythmSources: Array<["drums" | "bass" | "harmonic" | "vocals", string]> = [
      ["drums", row.rhythm?.drums ?? "none reported"],
      ["bass", row.rhythm?.bass ?? "none reported"],
      ["harmonic", row.rhythm?.harmonic ?? "none reported"],
      ["vocals", row.rhythm?.vocals ?? "none reported"],
    ];
    const detail = [
      `energy: ${row.energy != null ? row.energy : "not seeded"}`,
      `tension: ${row.tension != null ? row.tension : "not seeded"}`,
      ...rhythmSources.map(([k, v]) => `rhythm ${k}: ${v}`),
    ].join(" · ");
    return {
      id,
      start_s: row.start,
      end_s: row.end,
      label: row.label ?? id,
      laneLabel: "Segment Seeds",
      caption,
      reference: id,
      detail,
      summary:
        "experiments/segment_seeds — rule-based first-pass draft over the operator's segment spans; unreviewed inference, not operator input.",
      raw: row,
    };
  });
}

/**
 * Which intensity bucket a voiceness frame falls in — the SparseLane block
 * primitive has no continuous-curve renderer, so the "dense curve" this lane
 * needs is approximated by merging consecutive same-bucket frames (at the
 * file's native 50ms grid) into a run block, tinted on a single-hue ramp
 * (`sparseTints.ts`, hue 260) so a glance across the lane reads as a curve's
 * shape rather than five discrete colours. Bucket edges are round numbers,
 * not fit to any ground truth (none exists yet — see the experiment README).
 */
type VoicenessBucket = "veryLow" | "low" | "mid" | "high" | "veryHigh";

function voicenessBucket(v: number): VoicenessBucket {
  if (v >= 0.8) return "veryHigh";
  if (v >= 0.6) return "high";
  if (v >= 0.4) return "mid";
  if (v >= 0.2) return "low";
  return "veryLow";
}

const WHISPERX_VAD_BUCKET_TINT: Record<VoicenessBucket, string> = {
  veryLow: "whisperxVadVeryLow",
  low: "whisperxVadLow",
  mid: "whisperxVadMid",
  high: "whisperxVadHigh",
  veryHigh: "whisperxVadVeryHigh",
};

/**
 * whisperX's VAD front-end (speech-domain, `pyannote.audio` segmentation
 * model bundled locally — no gated checkpoint, no live token at analysis
 * time) over the vocal stem, run as its own pipeline service
 * (`whisperx_vad/`, promoted out of `experiments/` in v3.6 item 2). This
 * candidate's `vocal_phrase` spans carry real sub-second onsets (a
 * hysteresis binarizer over the segmentation model's own ~17ms frames), not
 * a clip-window approximation — see `whisperx_vad/model.py`. Diarization was
 * not attempted (no HF_TOKEN in this environment); this file carries no
 * diarization field at all.
 */
export function whisperxVadContent(file: WhisperxVadFile | null): SparseBlock[] {
  const out: SparseBlock[] = [];
  const frames = file?.frames ?? [];
  const intervalS = (file?.interval_ms ?? 50) / 1000;

  let runStart: number | null = null;
  let runBucket: VoicenessBucket | null = null;
  let runSum = 0;
  let runN = 0;
  let runIdx = 0;
  const flush = (endTime: number) => {
    if (runStart == null || runBucket == null || runN === 0) return;
    const avg = runSum / runN;
    runIdx += 1;
    out.push({
      id: `whisperx-vad-${runIdx}`,
      start_s: runStart,
      end_s: endTime,
      label: "",
      wideLabel: `voiceness ${avg.toFixed(2)}`,
      tintId: WHISPERX_VAD_BUCKET_TINT[runBucket],
      laneLabel: "Voice phrase (WhisperX VAD)",
      caption: `${formatRange(runStart, endTime)} · avg voiceness ${avg.toFixed(2)}`,
      reference: `whisperx-vad-${runIdx}`,
      detail: `${runN} frame${runN === 1 ? "" : "s"}`,
      summary: `whisperX VAD voiceness averaging ${avg.toFixed(2)} across this run.`,
      raw: { avg_voiceness: avg, n_frames: runN },
    });
  };

  for (const f of frames) {
    const bucket = voicenessBucket(f.voiceness);
    if (runBucket !== bucket) {
      flush(f.time_s);
      runStart = f.time_s;
      runBucket = bucket;
      runSum = 0;
      runN = 0;
    }
    runSum += f.voiceness;
    runN += 1;
  }
  if (frames.length > 0) {
    flush(frames[frames.length - 1]!.time_s + intervalS);
  }

  (file?.vocal_phrase ?? []).forEach((p, i) => {
    out.push({
      id: `whisperx-vad-phrase-${i + 1}`,
      start_s: p.start_s,
      end_s: p.end_s,
      label: "phrase",
      wideLabel: `VAD phrase${p.confidence != null ? ` · conf ${round(p.confidence, 2)}` : ""}`,
      tintId: "whisperxVadPhrase",
      laneLabel: "Voice phrase (WhisperX VAD)",
      caption: `${formatRange(p.start_s, p.end_s)} · VAD phrase`,
      reference: `whisperx-vad-phrase-${i + 1}`,
      detail: "vocal_phrase",
      summary:
        "A vocal_phrase span from whisperX's VAD hysteresis binarizer, with real sub-second onsets.",
      raw: p,
    });
  });

  out.sort((a, b) => a.start_s - b.start_s);
  return out;
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

// -- dispatch -------------------------------------------------------------

export interface LaneContentSources {
  humanHints?: HumanHintsFile | null;
  humanSections?: HumanSegmentsFile | null;
  moisesSections?: MoisesSegmentsFile | null;
  moisesLyrics?: MoisesLyricsFile | null;
  /** v3.4 item 5 — read-time overlay: Moises word-token ids the operator has
   *  hand-verified (from reference/human/lyric_validations.json). */
  lyricValidations?: ReadonlySet<number> | null;
  sections?: readonly SectionRow[];
  sectionSegmentation?: readonly SegmentationSection[];
  harmonicLayer?: HarmonicLayer | null;
  character?: CharacterFile | null;
  vocalTranscription?: VocalTranscriptionFile | null;
  vocalPhrases?: VocalPhrasesFile | null;
  arrangementState?: ArrangementStateFile | null;
  rhythmDrumIoi?: RhythmDrumIoiFile | null;
  rhythmStemAutocorr?: RhythmStemAutocorrFile | null;
  rhythmVocalOnsets?: RhythmVocalOnsetsFile | null;
  energyLevel?: EnergyLevelFile | null;
  tensionShape?: TensionShapeFile | null;
  segmentSeeds?: HumanSegmentsSeedFile | null;
  whisperxVad?: WhisperxVadFile | null;
  gestures?: EventTimeline | null;
}

/** the sparse (block) lane ids handled by this module, in registry order */
export const SPARSE_LANE_IDS = [
  "humanHints",
  "humanSections",
  "moisesSections",
  "allin1Sections",
  "moisesLyrics",
  "arrangementState",
  "vocalPhrases",
  "rhythmDrumIoi",
  "rhythmStemAutocorr",
  "rhythmVocalOnsets",
  "energyLevel",
  "tensionShape",
  "segmentSeeds",
  "whisperxVad",
  "gestures",
  "sections",
  "character",
  "vocalTranscription",
  "chordsInference",
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
    case "humanSections":
      return humanSectionsContent(s.humanSections ?? null);
    case "moisesSections":
      return moisesSectionsContent(s.moisesSections ?? null);
    case "allin1Sections":
      return allin1SectionsContent(s.sectionSegmentation ?? []);
    case "moisesLyrics":
      return moisesLyricsContent(s.moisesLyrics ?? null, s.lyricValidations ?? null);
    case "arrangementState":
      return arrangementStateContent(s.arrangementState ?? null);
    case "vocalPhrases":
      return vocalPhrasesContent(s.vocalPhrases ?? null);
    case "rhythmDrumIoi":
      return rhythmDrumIoiContent(s.rhythmDrumIoi ?? null);
    case "rhythmStemAutocorr":
      return rhythmStemAutocorrContent(s.rhythmStemAutocorr ?? null);
    case "rhythmVocalOnsets":
      return rhythmVocalOnsetsContent(s.rhythmVocalOnsets ?? null);
    case "energyLevel":
      return energyLevelContent(s.energyLevel ?? null);
    case "tensionShape":
      return tensionShapeContent(s.tensionShape ?? null);
    case "segmentSeeds":
      return segmentSeedsContent(s.segmentSeeds ?? null);
    case "whisperxVad":
      return whisperxVadContent(s.whisperxVad ?? null);
    case "gestures":
      return gesturesContent(s.gestures ?? null);
    case "sections":
      return sectionsContent(s.sections ?? [], s.sectionSegmentation ?? []);
    case "character":
      return characterContent(s.character ?? null);
    case "vocalTranscription":
      return vocalTranscriptionContent(s.vocalTranscription ?? null);
    case "chordsInference":
      return chordsInferenceContent(s.harmonicLayer ?? null);
    case "chords":
      return chordsContent(s.harmonicLayer ?? null);
    default:
      return [];
  }
}
