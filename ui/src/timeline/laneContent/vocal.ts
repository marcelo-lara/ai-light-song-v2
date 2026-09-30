// vocal.ts — Vocal Transcription, Vocal Cadence, Vocal Phrases and the
// WhisperX VAD voiceness lane. Split out of laneContent.ts (v3.9 item 7) with
// no behaviour change; see laneContent.ts for the dispatch table and shared
// SparseBlock type.

import type {
  VocalTranscriptionFile,
  VocalCadenceFile,
  VocalPhrasesFile,
  WhisperxVadFile,
} from "../../data/sparseArtifacts";
import type { SparseBlock } from "../laneContent";
import { formatRange, round } from "./shared";

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

function formatBarBeat(pos: { bar: number | null; beat: number | null; resolved: boolean }): string {
  if (pos.bar == null || pos.beat == null) return "no bar grid";
  return `bar ${pos.bar}.${pos.beat}${pos.resolved ? "" : " (unresolved)"}`;
}

/**
 * Line timing + call events from the published top-level `vocal_cadence.json`
 * (v3.9 item 1) — the operator's lyric alignment (`lyrics.json`) projected
 * onto `beats.json`. TIMING ONLY: no lyric text is read by this adapter or
 * carried by the underlying type — a line block shows bar position, duration
 * and token count; a call is a zero-length point marker with its own tint.
 */
export function vocalCadenceContent(file: VocalCadenceFile | null): SparseBlock[] {
  const lineBlocks: SparseBlock[] = (file?.lines ?? []).map((l, i) => ({
    id: `vocal-cadence-line-${i + 1}`,
    start_s: l.start_s,
    end_s: l.end_s,
    label: "",
    wideLabel: `${l.token_count} tokens${l.pickup ? " · pickup" : ""}`,
    laneLabel: "Vocal Cadence",
    caption: `${formatRange(l.start_s, l.end_s)} · ${formatBarBeat(l.start_position)} · ` +
      `${l.token_count} tokens` +
      (l.duration_beats == null ? "" : ` · ${round(l.duration_beats, 2)} beats`) +
      (l.pickup ? " · pickup" : ""),
    reference: `vocal-cadence-line-${i + 1}`,
    detail: `line ${l.line_id}`,
    summary: `vocal_cadence.json — line ${l.line_id}, ${formatBarBeat(l.start_position)} to ` +
      `${formatBarBeat(l.end_position)}, ${l.token_count} tokens, ` +
      (l.duration_beats == null ? "duration unresolved" : `${round(l.duration_beats, 2)} beats long`) +
      (l.pickup ? ", a pickup into its downbeat" : "") +
      ". Timing only — no lyric text is published or read.",
    raw: l,
  }));

  const callBlocks: SparseBlock[] = (file?.calls ?? []).map((c, i) => ({
    id: `vocal-cadence-call-${i + 1}`,
    start_s: c.time_s,
    end_s: c.time_s,
    label: "call",
    wideLabel: "call",
    tintId: "vocalCadenceCall",
    laneLabel: "Vocal Cadence",
    caption: `${c.time_s.toFixed(2)}s · ${formatBarBeat(c.position)} · call`,
    reference: `vocal-cadence-call-${i + 1}`,
    detail: "call",
    summary: `vocal_cadence.json — a call event (a parenthesised marker in the lyric ` +
      `alignment, e.g. a crowd shout) at ${formatBarBeat(c.position)}. No text is published.`,
    raw: c,
  }));

  return [...lineBlocks, ...callBlocks].sort((a, b) => a.start_s - b.start_s);
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
