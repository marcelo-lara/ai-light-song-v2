// referenceHints.ts — Human Hints, LLM Pending Proposals and Moises Lyrics
// lane adapters. Split out of laneContent.ts (v3.9 item 7) with no behaviour
// change; see laneContent.ts for the dispatch table and shared SparseBlock type.

import type {
  HumanHintsFile,
  PendingHintProposal,
  PendingProposalsFile,
} from "../../data/types";
import type { MoisesLyricsFile } from "../../data/sparseArtifacts";
import type { SparseBlock } from "../laneContent";
import { formatRange, round } from "./shared";

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
 * LLM Pending Proposals — `reference/proposals/pending.json`, written only by
 * `propose_hint` (mcp/proposals.py). Sits directly
 * under Human Hints so a proposal can be eyeballed against the hand-authored
 * hints it is auditioning to join. Only unreviewed proposals get a block here;
 * a decided (`approved`/`rejected`) proposal has already
 * left the queue this lane exists to surface.
 */
export function llmPendingProposalsContent(
  file: PendingProposalsFile | null,
): SparseBlock[] {
  return (file?.proposals ?? [])
    .filter(
      (p): p is PendingHintProposal => p.type === "hint" && p.status === "pending",
    )
    .map((p) => {
      const { start, end, title, summary } = p.hint;
      return {
        id: `llmPendingProposals-${p.id}`,
        start_s: start,
        end_s: end,
        label: title,
        wideLabel: title,
        laneLabel: "LLM Pending Proposals",
        caption: `${formatRange(start, end)} · ${title}`,
        reference: p.id,
        detail: p.evidence,
        summary,
        raw: p,
      };
    })
    .sort((a, b) => a.start_s - b.start_s);
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
