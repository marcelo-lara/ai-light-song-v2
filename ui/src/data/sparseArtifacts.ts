// sparseArtifacts.ts — types + tolerant parsers + loaders for the block-lane
// artifacts consumed by SparseLane (character, vocal transcription, vocal
// phrases, allin1 posterior shadow labels, whisperx vad,
// stem presence sections, vocal cadence, clap events, kick check, crash
// check, filter sweep, bar features, phrases, section names, and the top-level published arrangement state).
//
// These artifacts are still schema_version "1.0" and their exact shapes vary
// more than the essentia series, so the parsers here are deliberately tolerant:
// they coerce with `Number(x) || 0` / `String(x ?? "")` and never throw on a
// missing optional field. Quality of the structural read comes first, and a
// half-populated artifact should still render its blocks rather than hard-fail
// the whole lane (matches the previous app's `buildTimelineData` behaviour).
//
// The production Gestures lane reads `song_event_timeline.json` instead
// (typed `EventTimeline` in `./parsers` / `./types`, loaded via
// `loadEventTimeline`) -- plan v3.0 item 9 promoted it out of this file's
// generic tolerant-event machinery, which existed to also back the since-
// removed Machine Events / Identifier Hints lanes.

import { asObject } from "./parse";
import { artifactPaths } from "./paths";
import { loadJson, type LoadResult } from "./loaders";

const num = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};
const st = (v: unknown, fallback = ""): string =>
  typeof v === "string" ? v : v == null ? fallback : String(v);
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const rec = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" ? (v as Record<string, unknown>) : {};

// ---------------------------------------------------------------------------
// character blocks — reference/proposals/character.json
// ---------------------------------------------------------------------------
//
// What a passage is *like*, as distinct from where it sits in the arrangement,
// from `experiments/clap`. The worked example is `Armin - Revolution`'s
// hand-marked "Breath" block (81.4-96.3, "Vocal - no intense section") — a
// texture fact, not a verse/chorus fact, and one the operator gives its own
// fixture behaviour.
//
// Three sources, each used for what it is good at, and each named in `source`:
// `stems` for what is physically playing, `stems+clap` where CLAP's perceptual
// calm/intense axis is also required, and `allin1` for shadow labels — labels
// holding sustained frame-level posterior mass that allin1's own published
// segmentation never used.

export interface CharacterBlock {
  id: string;
  /** breath | void | vocal lead | full power | shadow <label> */
  kind: string;
  /** "stems" | "stems+clap" | "allin1" */
  source: string;
  start_s: number;
  end_s: number;
  /** per-kind evidence: stem levels and CLAP axis z-scores, or posterior shares */
  evidence: Record<string, number>;
  raw: Record<string, unknown>;
}

export interface CharacterFile {
  schema_version: string;
  song_name: string;
  blocks: CharacterBlock[];
}

export function parseCharacter(raw: unknown): CharacterFile {
  const o = asObject(raw, "reference/proposals/character.json");
  const blocks = arr(o.blocks).map((row, i): CharacterBlock => {
    const r = rec(row);
    const start_s = num(r.start_s);
    const evidenceIn = rec(r.evidence);
    const evidence: Record<string, number> = {};
    for (const [key, value] of Object.entries(evidenceIn)) {
      const n = Number(value);
      if (Number.isFinite(n)) evidence[key] = n;
    }
    return {
      id: st(r.id, `char-${String(i + 1).padStart(3, "0")}`),
      kind: st(r.kind, "unknown"),
      source: st(r.source, "stems"),
      start_s,
      end_s: Math.max(num(r.end_s, start_s), start_s),
      evidence,
      raw: r,
    };
  });
  blocks.sort((a, b) => a.start_s - b.start_s);
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    blocks,
  };
}

// ---------------------------------------------------------------------------
// vocal transcription — reference/proposals/vocal_transcription.json
// ---------------------------------------------------------------------------
//
// Sung lyrics with timing, from the two singing-voice-transcription experiments
// (`experiments/vocalparse`, `experiments/acestep_transcriber`) and their shared
// `whisper-large-v3` baseline. One file, one `sources` list keyed by model, so
// either experiment can rewrite its own row without touching the other's.
//
// Neither model emits reliable per-word seconds, so a source carries an
// `alignment` field: `words` means its text was aligned onto the baseline's
// word timeline, `span` / `native` / `unavailable` mean the line times are
// coarse or approximate. The lane shows that on every block rather than
// implying precision the model did not give.

export interface VocalLine {
  id: string;
  start_s: number;
  end_s: number;
  text: string;
  approx: boolean;
  confidence: number | null;
  raw: Record<string, unknown>;
}

export interface VocalStructureSpan {
  id: string;
  tag: string;
  instruments: string | null;
  start_s: number;
  end_s: number;
}

export interface VocalSource {
  model: string;
  /** "baseline" | "singing-transcription" */
  kind: string;
  /** "words" | "span" | "native" | "unavailable" | "" */
  alignment: string;
  alignment_reason: string | null;
  language: string | null;
  bpm: number | null;
  lines: VocalLine[];
  structure: VocalStructureSpan[];
}

export interface VocalTranscriptionFile {
  schema_version: string;
  song_name: string;
  sources: VocalSource[];
}

export function parseVocalTranscription(raw: unknown): VocalTranscriptionFile {
  const o = asObject(raw, "reference/proposals/vocal_transcription.json");
  const sources = arr(o.sources).map((row): VocalSource => {
    const r = rec(row);
    const lines = arr(r.lines).map((lrow, i): VocalLine => {
      const l = rec(lrow);
      const start_s = num(l.start_s);
      return {
        id: st(l.id, `line-${String(i + 1).padStart(3, "0")}`),
        start_s,
        end_s: Math.max(num(l.end_s, start_s), start_s),
        text: st(l.text),
        approx: l.approx === true,
        confidence: l.confidence == null ? null : num(l.confidence),
        raw: l,
      };
    });
    lines.sort((a, b) => a.start_s - b.start_s);
    const structure = arr(r.structure).map((srow, i): VocalStructureSpan => {
      const sp = rec(srow);
      const start_s = num(sp.start_s);
      return {
        id: st(sp.id, `struct-${String(i + 1).padStart(3, "0")}`),
        tag: st(sp.tag, "unknown"),
        instruments: sp.instruments == null ? null : st(sp.instruments),
        start_s,
        end_s: Math.max(num(sp.end_s, start_s), start_s),
      };
    });
    structure.sort((a, b) => a.start_s - b.start_s);
    return {
      model: st(r.model, "unknown"),
      kind: st(r.kind, "singing-transcription"),
      alignment: st(r.alignment),
      alignment_reason: r.alignment_reason == null ? null : st(r.alignment_reason),
      language: r.language == null ? null : st(r.language),
      bpm: r.bpm == null ? null : num(r.bpm),
      lines,
      structure,
    };
  });
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    sources,
  };
}

// ---------------------------------------------------------------------------
// Moises lyrics — reference/moises/lyrics.json
// ---------------------------------------------------------------------------
//
// An external, word-level sung-lyric export. The file is a flat array of word
// tokens, each carrying a `line_id`, `start`, `end` and per-word `confidence`;
// `<SOL>` / `<EOL>` marker rows delimit each line and carry no confidence. The
// lane renders one block per token — words and markers alike, ungrouped — so
// the raw transcription can be auditioned word by word against the audio.

export type MoisesTokenKind = "word" | "sol" | "eol";

export interface MoisesLyricToken {
  id: string;
  line_id: number;
  start_s: number;
  end_s: number;
  text: string;
  kind: MoisesTokenKind;
  /** per-word confidence in [0, 1], or null for the line markers */
  confidence: number | null;
  raw: Record<string, unknown>;
}

export interface MoisesLyricsFile {
  schema_version: string;
  song_name: string;
  tokens: MoisesLyricToken[];
}

const MOISES_MARKER_KIND: Record<string, MoisesTokenKind> = {
  "<SOL>": "sol",
  "<EOL>": "eol",
};

export function parseMoisesLyrics(raw: unknown): MoisesLyricsFile {
  const tokens = arr(raw).map((row, i): MoisesLyricToken => {
    const r = rec(row);
    const text = st(r.text).trim();
    const kind = MOISES_MARKER_KIND[text] ?? "word";
    const start_s = num(r.start);
    const conf = Number(r.confidence);
    return {
      id: st(r.id, `tok-${String(i + 1).padStart(4, "0")}`),
      line_id: num(r.line_id, 0),
      start_s,
      end_s: Math.max(num(r.end, start_s), start_s),
      text,
      kind,
      confidence: kind === "word" && Number.isFinite(conf) ? conf : null,
      raw: r,
    };
  });
  tokens.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: "", song_name: "", tokens };
}

// ---------------------------------------------------------------------------
// loaders
// ---------------------------------------------------------------------------

/** As above: absent until the exporter has been run over the song. */
export async function loadCharacter(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<CharacterFile>> {
  const result = await loadJson(artifactPaths.character(song), parseCharacter, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

/**
 * Shared by both singing-transcription experiments; absent until one of them
 * has exported over the song, so a 404 resolves to an empty file.
 */
export async function loadVocalTranscription(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<VocalTranscriptionFile>> {
  const result = await loadJson(
    artifactPaths.vocalTranscription(song),
    parseVocalTranscription,
    f,
  );
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, sources: [] } };
  }
  return result;
}
/**
 * External reference, present only for songs Moises has been run over, so a 404
 * resolves to an empty file. Every other failure still surfaces.
 */
export async function loadMoisesLyrics(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<MoisesLyricsFile>> {
  const result = await loadJson(
    artifactPaths.moisesLyrics(song),
    parseMoisesLyrics,
    f,
  );
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, tokens: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// vocal phrase blocks — reference/proposals/vocal_phrases.json
// ---------------------------------------------------------------------------
//
// Vocal-activity phrase / instrumental-gap / sustained-note blocks from
// experiments/vocal_phrases (Part A: the local-auto-gain hysteresis detector
// over the vocal stem; no model). Not ground truth — a proposal to audition
// against Human Hints and Moises Lyrics, which sit directly above it.

export interface VocalPhraseBlock {
  start_s: number;
  end_s: number;
  confidence: number;
  kind: "vocal_phrase" | "instrumental_gap" | "sustained_note";
  note_hz?: number;
}

export interface VocalPhrasesFile {
  schema_version: string;
  song_name: string;
  blocks: VocalPhraseBlock[];
}

export function parseVocalPhrases(raw: unknown): VocalPhrasesFile {
  const o = asObject(raw, "reference/proposals/vocal_phrases.json");
  const blocks: VocalPhraseBlock[] = [];
  for (const row of arr(o.vocal_phrases)) {
    const r = rec(row);
    blocks.push({ start_s: num(r.start), end_s: num(r.end), confidence: num(r.confidence), kind: "vocal_phrase" });
  }
  for (const row of arr(o.instrumental_gaps)) {
    const r = rec(row);
    blocks.push({ start_s: num(r.start), end_s: num(r.end), confidence: num(r.confidence), kind: "instrumental_gap" });
  }
  for (const row of arr(o.sustained_notes)) {
    const r = rec(row);
    blocks.push({
      start_s: num(r.start), end_s: num(r.end), confidence: num(r.confidence),
      kind: "sustained_note", note_hz: num(r.note_hz),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadVocalPhrases(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<VocalPhrasesFile>> {
  const result = await loadJson(artifactPaths.vocalPhrases(song), parseVocalPhrases, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// allin1 posterior shadow labels — reference/proposals/allin1_posterior.json
// ---------------------------------------------------------------------------
//
// Spans where a non-argmax allin1 frame-posterior label sustains a share the
// published 8-bar argmax discards (e.g. Armin's `break`, 30% of the posterior
// across 143-175s, unrepresented in sections.json). experiments/allin1_posterior,
// no model run — reads the already-cached allin1 posterior. Not ground truth,
// and per docs/experiments.md not yet a promotion candidate (loses to an
// even-grid baseline on boundary recall on 3/4 gold songs) — a proposal to
// audition against Sections, nothing more.

export interface Allin1PosteriorBlock {
  start_s: number;
  end_s: number;
  label: string;
  mean_share: number;
  published_overlap: number;
}

export interface Allin1PosteriorFile {
  schema_version: string;
  song_name: string;
  blocks: Allin1PosteriorBlock[];
}

export function parseAllin1Posterior(raw: unknown): Allin1PosteriorFile {
  const o = asObject(raw, "reference/proposals/allin1_posterior.json");
  const blocks: Allin1PosteriorBlock[] = [];
  for (const row of arr(o.shadow_labels)) {
    const r = rec(row);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      label: st(r.label),
      mean_share: num(r.mean_share),
      published_overlap: num(r.published_overlap),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadAllin1Posterior(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<Allin1PosteriorFile>> {
  const result = await loadJson(artifactPaths.allin1Posterior(song), parseAllin1Posterior, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// stem presence sections — reference/proposals/stem_presence_sections.json
// ---------------------------------------------------------------------------
//
// experiments/stem_presence_sections: a low-cardinality bass/drums-presence
// state machine (full / bass_only / drums_only / stripped), hysteresis-merged
// (a short mid-section dip does not split it) and boundary-refined to the
// nearest physical stem onset in loudness.json. Vocals never cut a boundary —
// `vocals_present_fraction` is annotation only. A proposal to audition
// against Human Hints, never ground truth; not yet scored corpus-wide.

export interface StemPresenceSectionsBlock {
  start_s: number;
  end_s: number;
  bar_start: number;
  bar_end: number;
  state: string;
  drums_detail: string;
  vocals_present_fraction: number;
  confidence: number | null;
  boundary_resolved: boolean | null;
}

export interface StemPresenceSectionsFile {
  schema_version: string;
  song_name: string;
  blocks: StemPresenceSectionsBlock[];
}

export function parseStemPresenceSections(raw: unknown): StemPresenceSectionsFile {
  const o = asObject(raw, "reference/proposals/stem_presence_sections.json");
  const blocks: StemPresenceSectionsBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      bar_start: num(r.bar_start),
      bar_end: num(r.bar_end),
      state: st(r.state),
      drums_detail: st(r.drums_detail),
      vocals_present_fraction: num(r.vocals_present_fraction),
      confidence: r.confidence == null ? null : num(r.confidence),
      boundary_resolved: typeof r.boundary_resolved === "boolean" ? r.boundary_resolved : null,
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadStemPresenceSections(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<StemPresenceSectionsFile>> {
  const result = await loadJson(
    artifactPaths.stemPresenceSections(song), parseStemPresenceSections, f,
  );
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// vocal cadence — top-level vocal_cadence.json (v3.9 item 1)
// ---------------------------------------------------------------------------
//
// Published per-line bar-relative timing and separate call events from the
// operator's lyric alignment (`reference/human/lyrics.json`, else
// `reference/moises/lyrics.json`) + `beats.json`. TIMING ONLY — no lyric text
// is published here or read by this parser. `source: null` + `reason` set
// (D1.1) when the song carries no lyrics tier — `lines`/`calls` are then
// empty, never inferred.

export interface VocalCadencePosition {
  bar: number | null;
  beat: number | null;
  resolved: boolean;
}

export interface VocalCadenceLine {
  line_id: number;
  start_s: number;
  end_s: number;
  start_position: VocalCadencePosition;
  end_position: VocalCadencePosition;
  duration_beats: number | null;
  token_count: number;
  pickup: boolean;
}

export interface VocalCadenceCall {
  time_s: number;
  position: VocalCadencePosition;
}

export interface VocalCadenceFile {
  schema_version: string;
  song_name: string;
  /** "human" | "moises" — which lyrics.json tier fed this file; "" (coerced
   * from `null`) when the song has neither (D1.1) — see `reason`. */
  source: string;
  /** Set only in the D1.1 no-lyrics case; `null` otherwise. */
  reason: string | null;
  lines: VocalCadenceLine[];
  calls: VocalCadenceCall[];
}

function parseVocalCadencePosition(raw: unknown): VocalCadencePosition {
  const r = rec(raw);
  return {
    bar: r.bar == null ? null : num(r.bar),
    beat: r.beat == null ? null : num(r.beat),
    resolved: r.resolved === true,
  };
}

export function parseVocalCadence(raw: unknown): VocalCadenceFile {
  const o = asObject(raw, "vocal_cadence.json");
  const lines: VocalCadenceLine[] = [];
  for (const row of arr(o.lines)) {
    const r = rec(row);
    lines.push({
      line_id: num(r.line_id),
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      start_position: parseVocalCadencePosition(r.start_position),
      end_position: parseVocalCadencePosition(r.end_position),
      duration_beats: r.duration_beats == null ? null : num(r.duration_beats),
      token_count: num(r.token_count),
      pickup: r.pickup === true,
    });
  }
  lines.sort((a, b) => a.start_s - b.start_s);

  const calls: VocalCadenceCall[] = [];
  for (const row of arr(o.calls)) {
    const r = rec(row);
    calls.push({ time_s: num(r.time_s), position: parseVocalCadencePosition(r.position) });
  }
  calls.sort((a, b) => a.time_s - b.time_s);

  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    source: st(o.source),
    reason: o.reason == null ? null : st(o.reason),
    lines,
    calls,
  };
}

export async function loadVocalCadence(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<VocalCadenceFile>> {
  const result = await loadJson(artifactPaths.vocalCadence(song), parseVocalCadence, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    // vocal_cadence.json is a required top-level file as of v3.9 item 1; a
    // 404 only happens on a song analysed before that item shipped and not
    // yet backfilled with `--stage publish-vocal-cadence`. Tolerant empty
    // read rather than a hard failure, same convention as every other
    // artifact this file parses.
    return {
      ok: true,
      data: { schema_version: "", song_name: song, source: "", reason: "not yet published for this song", lines: [], calls: [] },
    };
  }
  return result;
}

// ---------------------------------------------------------------------------
// arrangement state — arrangement_state.json (top-level, published)
// ---------------------------------------------------------------------------
//
// Who-is-playing state-change blocks from the production
// `detect-arrangement-state` stage, published to the top-level
// `arrangement_state.json` — derived from the published per-stem RMS series,
// no audio, no model. `margin_db` is the dB headroom at the stem flip and
// `confidence` is its bounded-exponential squash; both are `null` on the
// leading block, which has no flip. Optional per song (a pre-v3.2 analysis
// will not have the file).

export interface ArrangementStateBlock {
  start_s: number;
  end_s: number;
  playing: string[];
  entered: string[];
  left: string[];
  margin_db: number | null;
  confidence: number | null;
}

export interface ArrangementStateFile {
  schema_version: string;
  song_name: string;
  blocks: ArrangementStateBlock[];
}

export function parseArrangementState(raw: unknown): ArrangementStateFile {
  const o = asObject(raw, "arrangement_state.json");
  const blocks: ArrangementStateBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    const marginRaw = r.margin_db;
    const confRaw = r.confidence;
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      playing: arr(r.playing).map((x) => st(x)),
      entered: arr(r.entered).map((x) => st(x)),
      left: arr(r.left).map((x) => st(x)),
      margin_db: typeof marginRaw === "number" && Number.isFinite(marginRaw) ? marginRaw : null,
      confidence: typeof confRaw === "number" && Number.isFinite(confRaw) ? confRaw : null,
    });
  }
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadArrangementState(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<ArrangementStateFile>> {
  const result = await loadJson(artifactPaths.arrangementState(song), parseArrangementState, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}


// ---------------------------------------------------------------------------
// whisperxVad — artifacts/whisperx-vad/whisperx_vad.json
// ---------------------------------------------------------------------------
//
// whisperX's VAD front-end (speech-domain, not music or a general
// audio-tagging class), run over the vocal stem only, as its own pipeline
// service (`whisperx_vad/`, v3.6 item 2 — promoted out of `experiments/`,
// no longer read from `reference/proposals/`). A per-50ms-frame `voiceness`
// score in [0,1] plus `vocal_phrase` spans. `interval_ms` is 50: VAD spans
// carry real sub-second onsets/offsets (a hysteresis binarizer over the
// segmentation model's own ~17ms frames), so `vocal_phrase` boundaries are
// genuinely timed, not a clip-window approximation. Diarization was NOT
// attempted (no HF_TOKEN in this environment, and a live-token dependency at
// analysis time is an automatic kill regardless of score) — no diarization
// field exists in this file at all, never a stubbed-out null.

export interface VoicenessFrameRow {
  time_s: number;
  voiceness: number;
  confidence: number | null;
}

export interface WhisperxVadFile {
  schema_version: string;
  song_name: string;
  interval_ms: number;
  frames: VoicenessFrameRow[];
  vocal_phrase: { start_s: number; end_s: number; confidence: number | null }[];
}

export function parseWhisperxVad(raw: unknown): WhisperxVadFile {
  const o = asObject(raw, "artifacts/whisperx-vad/whisperx_vad.json");
  const meta = rec(o.metadata);
  const frames = arr(o.frames).map((row): VoicenessFrameRow => {
    const r = rec(row);
    return {
      time_s: num(r.time),
      voiceness: num(r.voiceness),
      confidence: r.confidence == null ? null : num(r.confidence),
    };
  });
  const vocal_phrase = arr(o.vocal_phrase).map((row) => {
    const r = rec(row);
    const start_s = num(r.start);
    return {
      start_s,
      end_s: Math.max(num(r.end, start_s), start_s),
      confidence: r.confidence == null ? null : num(r.confidence),
    };
  });
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    interval_ms: num(meta.interval_ms, 50),
    frames,
    vocal_phrase,
  };
}

export async function loadWhisperxVad(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<WhisperxVadFile>> {
  const result = await loadJson(artifactPaths.whisperxVad(song), parseWhisperxVad, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return {
      ok: true,
      data: { schema_version: "", song_name: song, interval_ms: 50, frames: [], vocal_phrase: [] },
    };
  }
  return result;
}

// ---------------------------------------------------------------------------
// clapEvents — reference/proposals/clap_events.json
// ---------------------------------------------------------------------------
//
// v3.9 item 2: claps detected from the drums stem by per-hit spectral shape
// (1-6 kHz noise share, 120-400 Hz body share), never omnizart's label.
// `experiments/clap_events`. Point events — a proposal to audition, not
// ground truth.

export interface ClapEvent {
  time: number;
  noise_share: number;
  body_share: number;
  confidence: number | null;
}

export interface ClapEventsFile {
  schema_version: string;
  song_name: string;
  events: ClapEvent[];
}

export function parseClapEvents(raw: unknown): ClapEventsFile {
  const o = asObject(raw, "reference/proposals/clap_events.json");
  const events: ClapEvent[] = [];
  for (const row of arr(o.events)) {
    const r = rec(row);
    events.push({
      time: num(r.time),
      noise_share: num(r.noise_share),
      body_share: num(r.body_share),
      confidence: r.confidence == null ? null : num(r.confidence),
    });
  }
  events.sort((a, b) => a.time - b.time);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), events };
}

export async function loadClapEvents(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<ClapEventsFile>> {
  const result = await loadJson(artifactPaths.clapEvents(song), parseClapEvents, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, events: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// kickCheck — reference/proposals/kick_check.json
// ---------------------------------------------------------------------------
//
// v3.9 item 2 (kick-check sibling): every omnizart `kick` event kept or
// rejected by the same per-hit spectral shape as clapEvents, plus a
// percussive-attack gate. `experiments/kick_check`.

export interface KickCheckHit {
  time: number;
  verdict: string; // "keep" | "reject"
  low_share: number;
  noise_share: number;
}

export interface KickCheckFile {
  schema_version: string;
  song_name: string;
  kicks: KickCheckHit[];
}

export function parseKickCheck(raw: unknown): KickCheckFile {
  const o = asObject(raw, "reference/proposals/kick_check.json");
  const kicks: KickCheckHit[] = [];
  for (const row of arr(o.kicks)) {
    const r = rec(row);
    kicks.push({
      time: num(r.time),
      verdict: st(r.verdict, "reject"),
      low_share: num(r.low_share),
      noise_share: num(r.noise_share),
    });
  }
  kicks.sort((a, b) => a.time - b.time);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), kicks };
}

export async function loadKickCheck(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<KickCheckFile>> {
  const result = await loadJson(artifactPaths.kickCheck(song), parseKickCheck, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, kicks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// crashCheck — reference/proposals/crash_check.json
// ---------------------------------------------------------------------------
//
// The "crash over-fires on bright hats/rides" bug (v3.9): every omnizart
// `crash` event kept or rejected by regular-stream-period rejection plus a
// brilliance-band decay-shape gate. `experiments/crash_check`.

export interface CrashCheckHit {
  time: number;
  verdict: string; // "keep" | "reject"
  is_stream_continuation: boolean;
  decay_ratio: number | null;
}

export interface CrashCheckFile {
  schema_version: string;
  song_name: string;
  crashes: CrashCheckHit[];
}

export function parseCrashCheck(raw: unknown): CrashCheckFile {
  const o = asObject(raw, "reference/proposals/crash_check.json");
  const crashes: CrashCheckHit[] = [];
  for (const row of arr(o.crashes)) {
    const r = rec(row);
    crashes.push({
      time: num(r.time),
      verdict: st(r.verdict, "reject"),
      is_stream_continuation: r.is_stream_continuation === true,
      decay_ratio: r.decay_ratio == null ? null : num(r.decay_ratio),
    });
  }
  crashes.sort((a, b) => a.time - b.time);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), crashes };
}

export async function loadCrashCheck(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<CrashCheckFile>> {
  const result = await loadJson(artifactPaths.crashCheck(song), parseCrashCheck, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, crashes: [] } };
  }
  return result;
}


// ---------------------------------------------------------------------------
// filterSweep — reference/proposals/filter_sweep.json
// ---------------------------------------------------------------------------
//
// v3.10 item 14: a harmonic or bass stem changing tone — spectral centroid
// moving near-monotonically over 2-16 bars while that stem's loudness stays
// level. `experiments/filter_sweep`. A proposal, not ground truth.

export interface FilterSweepBlock {
  start_s: number;
  end_s: number;
  direction: string; // "opening" | "closing"
  stem: string; // "harmonic" | "bass"
  depth: number; // centroid change, octaves
  confidence: number | null;
}

export interface FilterSweepFile {
  schema_version: string;
  song_name: string;
  blocks: FilterSweepBlock[];
}

export function parseFilterSweep(raw: unknown): FilterSweepFile {
  const o = asObject(raw, "reference/proposals/filter_sweep.json");
  const blocks: FilterSweepBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      direction: st(r.direction),
      stem: st(r.stem),
      depth: num(r.depth),
      confidence: r.confidence == null ? null : num(r.confidence),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadFilterSweep(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<FilterSweepFile>> {
  const result = await loadJson(artifactPaths.filterSweep(song), parseFilterSweep, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}


// ---------------------------------------------------------------------------
// barFeatures — reference/proposals/bar_features.json
// ---------------------------------------------------------------------------
//
// v3.12 item 1: one row per bar fusing existing artifacts (loudness, FFT bands,
// brightness, transients, drum counts, vocals cover, arrangement entries,
// sweeps, gestures). `experiments/bar_features`. A feature table, not a claim.
// Only `bars[]` is read here; `half_beats[]` is for later detectors.

export interface BarFeatureRow {
  bar: number;
  start_s: number;
  end_s: number;
  beats_in_bar: number;
  irregular: boolean;
  mix_rms: number | null;
  bass_rms: number | null;
  drums_rms: number | null;
  harmonic_rms: number | null;
  vocals_rms: number | null;
  brightness: number | null;
  transient_mean: number | null;
  transient_std: number | null;
  kick: number;
  snare: number;
  hat: number;
  vocals_cover: number;
  entered: string[];
  left: string[];
  sweep_opening: number;
  sweep_closing: number;
  gestures: string[];
}

export interface BarFeaturesFile {
  schema_version: string;
  song_name: string;
  bars: BarFeatureRow[];
}

const numOrNull = (v: unknown): number | null => (v == null ? null : num(v));

export function parseBarFeatures(raw: unknown): BarFeaturesFile {
  const o = asObject(raw, "reference/proposals/bar_features.json");
  const bars: BarFeatureRow[] = [];
  for (const row of arr(o.bars)) {
    const r = rec(row);
    const loud = rec(r.loud_rms);
    const sweep = rec(r.sweep);
    bars.push({
      bar: num(r.bar),
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      beats_in_bar: num(r.beats_in_bar),
      irregular: r.irregular === true,
      mix_rms: numOrNull(loud.mix),
      bass_rms: numOrNull(loud.bass),
      drums_rms: numOrNull(loud.drums),
      harmonic_rms: numOrNull(loud.harmonic),
      vocals_rms: numOrNull(loud.vocals),
      brightness: numOrNull(r.brightness),
      transient_mean: numOrNull(r.transient_mean),
      transient_std: numOrNull(r.transient_std),
      kick: num(r.kick),
      snare: num(r.snare),
      hat: num(r.hat),
      vocals_cover: num(r.vocals_cover),
      entered: arr(r.entered).map((x) => st(x)),
      left: arr(r.left).map((x) => st(x)),
      sweep_opening: num(sweep.opening),
      sweep_closing: num(sweep.closing),
      gestures: Object.keys(rec(r.gestures)),
    });
  }
  bars.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), bars };
}

export async function loadBarFeatures(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<BarFeaturesFile>> {
  const result = await loadJson(artifactPaths.barFeatures(song), parseBarFeatures, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, bars: [] } };
  }
  return result;
}


// ---------------------------------------------------------------------------
// phrases — reference/proposals/phrases.json
// ---------------------------------------------------------------------------
//
// v3.10 item 15: the song cut where the audio changes (stem entries/exits,
// impacts, pre-drop gaps, riser / snare-roll ends), each edge at the nearest
// trusted beat; never bar-counted. `experiments/phrases`. A proposal, not
// ground truth. `resolved: false` = the evidence for an edge disagrees.

export interface PhraseEdge {
  score: number;
  onset_s: number;
  snapped: boolean;
  kinds: string[];
}

export interface PhraseSweep {
  stem: string;
  direction: string;
  start_s: number;
  end_s: number;
}

export interface PhrasesBlock {
  id: string;
  start_s: number;
  end_s: number;
  n_beats: number;
  kick_presence: number | null;
  bass_presence: number | null;
  vocals_presence: number | null;
  riser_density: number | null;
  snare_roll_density: number | null;
  filter_sweeps: PhraseSweep[] | null; // null = filter_sweep.json was absent
  noise_sweep: boolean | null;
  noise_sweep_strength: number | null;
  kick_dropout_near_end: boolean | null;
  ends_on_gap: boolean;
  repeat_of: string | null;
  repeat_distance: number | null;
  resolved: boolean;
  conflicts: string[];
  confidence: number | null;
  start_edge: PhraseEdge | null;
  end_edge: PhraseEdge | null;
}

export interface PhrasesFile {
  schema_version: string;
  song_name: string;
  blocks: PhrasesBlock[];
}

function optNum(v: unknown): number | null {
  return v == null ? null : num(v);
}

function optBool(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
}

function parsePhraseEdge(v: unknown): PhraseEdge | null {
  if (v == null) return null;
  const r = rec(v);
  return {
    score: num(r.score),
    onset_s: num(r.onset_s),
    snapped: r.snapped === true,
    kinds: arr(r.kinds).map((k) => st(k)),
  };
}

export function parsePhrases(raw: unknown): PhrasesFile {
  const o = asObject(raw, "reference/proposals/phrases.json");
  const blocks: PhrasesBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({
      id: st(r.id),
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      n_beats: num(r.n_beats),
      kick_presence: optNum(r.kick_presence),
      bass_presence: optNum(r.bass_presence),
      vocals_presence: optNum(r.vocals_presence),
      riser_density: optNum(r.riser_density),
      snare_roll_density: optNum(r.snare_roll_density),
      filter_sweeps:
        r.filter_sweeps == null
          ? null
          : arr(r.filter_sweeps).map((x) => {
              const s = rec(x);
              return {
                stem: st(s.stem),
                direction: st(s.direction),
                start_s: num(s.start_s),
                end_s: num(s.end_s),
              };
            }),
      noise_sweep: optBool(r.noise_sweep),
      noise_sweep_strength: optNum(r.noise_sweep_strength),
      kick_dropout_near_end: optBool(r.kick_dropout_near_end),
      ends_on_gap: r.ends_on_gap === true,
      repeat_of: r.repeat_of == null ? null : st(r.repeat_of),
      repeat_distance: optNum(r.repeat_distance),
      resolved: r.resolved !== false,
      conflicts: arr(r.conflicts).map((c) => st(c)),
      confidence: optNum(r.confidence),
      start_edge: parsePhraseEdge(r.start_edge),
      end_edge: parsePhraseEdge(r.end_edge),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadPhrases(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<PhrasesFile>> {
  const result = await loadJson(artifactPaths.phrases(song), parsePhrases, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}


// ---------------------------------------------------------------------------
// sectionNames — reference/proposals/section_names.json
// ---------------------------------------------------------------------------
//
// v3.10 item 17: `experiments/section_names` names every phrase by its place
// in the typical EDM sequence, boundaries on item 15's phrase edges. A song
// with no build->drop unit keeps its current `sections.json` labels
// (`status: "kept_current"`, `source: "sections.json"`). A proposal, not truth.

export interface SectionNamesBlock {
  id: string;
  start_s: number;
  end_s: number;
  label: string;
  confidence: number | null;
  why: string[];
  unit: string | null;
  phrase_ids: string[];
  start_kind: string;
  inherited_from: string | null;
  source: string;
}

export interface SectionNamesUnit {
  id: string;
  kind: string;
  label: string;
  drop_start_s: number;
  confidence: number | null;
}

export interface SectionNamesFile {
  schema_version: string;
  song_name: string;
  status: string;
  status_reason: string | null;
  units: SectionNamesUnit[];
  blocks: SectionNamesBlock[];
}

export function parseSectionNames(raw: unknown): SectionNamesFile {
  const o = asObject(raw, "reference/proposals/section_names.json");
  const blocks: SectionNamesBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({
      id: st(r.id),
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      label: st(r.label),
      confidence: optNum(r.confidence),
      why: arr(r.why).map((w) => st(w)),
      unit: r.unit == null ? null : st(r.unit),
      phrase_ids: arr(r.phrase_ids).map((p) => st(p)),
      start_kind: st(r.start_kind),
      inherited_from: r.inherited_from == null ? null : st(r.inherited_from),
      source: st(r.source),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  const units = arr(o.units).map((u) => {
    const r = rec(u);
    return {
      id: st(r.id),
      kind: st(r.kind),
      label: st(r.label),
      drop_start_s: num(r.drop_start_s),
      confidence: optNum(r.confidence),
    };
  });
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    status: st(o.status),
    status_reason: o.status_reason == null ? null : st(o.status_reason),
    units,
    blocks,
  };
}

export async function loadSectionNames(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<SectionNamesFile>> {
  const result = await loadJson(artifactPaths.sectionNames(song), parseSectionNames, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return {
      ok: true,
      data: { schema_version: "", song_name: song, status: "", status_reason: null, units: [], blocks: [] },
    };
  }
  return result;
}
