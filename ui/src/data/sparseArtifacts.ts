// sparseArtifacts.ts — types + tolerant parsers + loaders for the block-lane
// artifacts consumed by SparseLane (character, vocal transcription, vocal
// phrases, phrase periodicity, rhythm drum ioi, rhythm stem autocorr, rhythm
// vocal onsets, energy level, tension shape, whisperx vad, voice
// multiplicity, and the top-level published arrangement state).
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
// phrasePeriodicity — reference/proposals/phrase_periodicity.json
// ---------------------------------------------------------------------------
//
// One block per operator hint (or published section) from
// experiments/phrase_periodicity: z-normalised per-bar 16-slot energy profiles
// autocorrelated over 1-16 bar lags (period only, never phase). Each block
// carries a repetition `regime` and a `period` in bars — `period` is null when
// no repeat structure was detected, and renders as "no phrase structure
// detected", never a fabricated number. A proposal to audition against Human
// Hints, not ground truth. The experiment PASSED its kill condition.

export interface PhrasePeriodicityBlock {
  start_s: number;
  end_s: number;
  title: string;
  regime: string;
  /** repeat unit in bars (1 / 0.5), or null when no phrase structure detected */
  period: number | null;
  n_bars: number;
}

export interface PhrasePeriodicityFile {
  schema_version: string;
  song_name: string;
  blocks: PhrasePeriodicityBlock[];
}

export function parsePhrasePeriodicity(raw: unknown): PhrasePeriodicityFile {
  const o = asObject(raw, "reference/proposals/phrase_periodicity.json");
  const blocks: PhrasePeriodicityBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      title: st(r.title),
      regime: st(r.regime),
      period: r.period == null ? null : num(r.period),
      n_bars: num(r.n_bars),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadPhrasePeriodicity(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<PhrasePeriodicityFile>> {
  const result = await loadJson(artifactPaths.phrasePeriodicity(song), parsePhrasePeriodicity, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// rhythmDrumIoi — reference/proposals/rhythm_drum_ioi.json
// ---------------------------------------------------------------------------
//
// v3.6 item 5/6a: candidate `rhythm.drums` producer from
// experiments/rhythm_drum_ioi — dominant drum_events.json inter-onset
// interval / local beat period -> nearest subdivision. A proposal to
// audition, not ground truth; `confidence` is per-source, never a constant.

export interface RhythmDrumIoiBlock {
  start_s: number;
  end_s: number;
  subdivisions: Record<string, string>;
  confidence: Record<string, number>;
  onsets_per_bar: number;
}

export interface RhythmDrumIoiFile {
  schema_version: string;
  song_name: string;
  blocks: RhythmDrumIoiBlock[];
}

export function parseRhythmDrumIoi(raw: unknown): RhythmDrumIoiFile {
  const o = asObject(raw, "reference/proposals/rhythm_drum_ioi.json");
  const blocks: RhythmDrumIoiBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    const subs = rec(r.subdivisions);
    const confs = rec(r.confidence);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      subdivisions: Object.fromEntries(Object.entries(subs).map(([k, v]) => [k, st(v)])),
      confidence: Object.fromEntries(Object.entries(confs).map(([k, v]) => [k, num(v)])),
      onsets_per_bar: num(r.onsets_per_bar),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadRhythmDrumIoi(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<RhythmDrumIoiFile>> {
  const result = await loadJson(artifactPaths.rhythmDrumIoi(song), parseRhythmDrumIoi, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// rhythmStemAutocorr — reference/proposals/rhythm_stem_autocorr.json
// ---------------------------------------------------------------------------
//
// v3.6 item 5/6b: candidate `rhythm.{drums,bass,harmonic,vocals}` producer
// from experiments/rhythm_stem_autocorr — sub-beat autocorrelation of each
// stem's 20 ms loudness. `vocals` reads `"none"` where no vocals_phrase
// overlaps, not omitted. A proposal to audition, not ground truth.

export interface RhythmStemAutocorrBlock {
  start_s: number;
  end_s: number;
  subdivisions: Record<string, string>;
  confidence: Record<string, number>;
}

export interface RhythmStemAutocorrFile {
  schema_version: string;
  song_name: string;
  blocks: RhythmStemAutocorrBlock[];
}

export function parseRhythmStemAutocorr(raw: unknown): RhythmStemAutocorrFile {
  const o = asObject(raw, "reference/proposals/rhythm_stem_autocorr.json");
  const blocks: RhythmStemAutocorrBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    const subs = rec(r.subdivisions);
    const confs = rec(r.confidence);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      subdivisions: Object.fromEntries(Object.entries(subs).map(([k, v]) => [k, st(v)])),
      confidence: Object.fromEntries(Object.entries(confs).map(([k, v]) => [k, num(v)])),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadRhythmStemAutocorr(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<RhythmStemAutocorrFile>> {
  const result = await loadJson(artifactPaths.rhythmStemAutocorr(song), parseRhythmStemAutocorr, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// rhythmVocalOnsets — reference/proposals/rhythm_vocal_onsets.json
// ---------------------------------------------------------------------------
//
// v3.6 item 5/6c: candidate `rhythm.vocals` + `onsets_per_beat` producer from
// experiments/rhythm_vocal_onsets — dominant whisper word-onset interval /
// local beat period -> nearest subdivision. `compute` runs only in the
// ACE-Step sandbox image. A proposal to audition, not ground truth.

export interface RhythmVocalOnsetsBlock {
  start_s: number;
  end_s: number;
  subdivisions: Record<string, string>;
  confidence: Record<string, number>;
  onsets_per_beat: number | null;
}

export interface RhythmVocalOnsetsFile {
  schema_version: string;
  song_name: string;
  blocks: RhythmVocalOnsetsBlock[];
}

export function parseRhythmVocalOnsets(raw: unknown): RhythmVocalOnsetsFile {
  const o = asObject(raw, "reference/proposals/rhythm_vocal_onsets.json");
  const blocks: RhythmVocalOnsetsBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    const subs = rec(r.subdivisions);
    const confs = rec(r.confidence);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      subdivisions: Object.fromEntries(Object.entries(subs).map(([k, v]) => [k, st(v)])),
      confidence: Object.fromEntries(Object.entries(confs).map(([k, v]) => [k, num(v)])),
      onsets_per_beat: r.onsets_per_beat == null ? null : num(r.onsets_per_beat),
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadRhythmVocalOnsets(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<RhythmVocalOnsetsFile>> {
  const result = await loadJson(artifactPaths.rhythmVocalOnsets(song), parseRhythmVocalOnsets, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// energyLevel — reference/proposals/energy_level.json
// ---------------------------------------------------------------------------
//
// v3.6 item 5/6: candidate `energy` (1-5) producer from
// experiments/energy_level — segment mix loudness + stems-playing fraction,
// song-relative quintile-binned. A proposal to audition, not ground truth.

export interface EnergyLevelBlock {
  start_s: number;
  end_s: number;
  energy: number;
  confidence: number;
  evidence: { mix_mean: number; stems_fraction: number };
}

export interface EnergyLevelFile {
  schema_version: string;
  song_name: string;
  blocks: EnergyLevelBlock[];
}

export function parseEnergyLevel(raw: unknown): EnergyLevelFile {
  const o = asObject(raw, "reference/proposals/energy_level.json");
  const blocks: EnergyLevelBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    const ev = rec(r.evidence);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      energy: num(r.energy),
      confidence: num(r.confidence),
      evidence: { mix_mean: num(ev.mix_mean), stems_fraction: num(ev.stems_fraction) },
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadEnergyLevel(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<EnergyLevelFile>> {
  const result = await loadJson(artifactPaths.energyLevel(song), parseEnergyLevel, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// tensionShape — reference/proposals/tension_shape.json
// ---------------------------------------------------------------------------
//
// v3.6 item 5/6: candidate `tension` (1-5) producer from
// experiments/tension_shape — energy slope across the span + gesture
// build/tension overlap + phrase_periodicity through-composed regime
// overlap. A proposal to audition, not ground truth.

export interface TensionShapeBlock {
  start_s: number;
  end_s: number;
  tension: number;
  confidence: number;
  evidence: {
    slope: number;
    gesture_bump: boolean;
    phrase_periodicity_through_composed_bump: boolean;
  };
}

export interface TensionShapeFile {
  schema_version: string;
  song_name: string;
  blocks: TensionShapeBlock[];
}

export function parseTensionShape(raw: unknown): TensionShapeFile {
  const o = asObject(raw, "reference/proposals/tension_shape.json");
  const blocks: TensionShapeBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    const ev = rec(r.evidence);
    blocks.push({
      start_s: num(r.start_s),
      end_s: num(r.end_s),
      tension: num(r.tension),
      confidence: num(r.confidence),
      evidence: {
        slope: num(ev.slope),
        gesture_bump: Boolean(ev.gesture_bump),
        phrase_periodicity_through_composed_bump: Boolean(
          ev.phrase_periodicity_through_composed_bump,
        ),
      },
    });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadTensionShape(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<TensionShapeFile>> {
  const result = await loadJson(artifactPaths.tensionShape(song), parseTensionShape, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// vocalVoiceness — reference/proposals/vocal_voiceness.json
// ---------------------------------------------------------------------------
//
// The `voiceness_common.schema` proposal shape shared by every voiceness
// candidate (items 4-7 — this file is item 4, `experiments/vocal_voiceness`):
// a per-50ms-frame `voiceness` score in [0,1] (vibrato + portamento +
// sibilance, noisy-OR combined — see the experiment's `model.py`) plus
// `vocal_phrase` spans derived with a pitch-continuity bridge over
// `vocal_phrases`' known `sustained_notes` gap. Not ground truth — a
// proposal to audition against Human Hints; kill condition unevaluable until
// item 1's `type: "vocal"` ground truth exists (see the experiment README).

export interface VoicenessFrameRow {
  time_s: number;
  voiceness: number;
  confidence: number | null;
}

export interface VocalVoicenessFile {
  schema_version: string;
  song_name: string;
  interval_ms: number;
  frames: VoicenessFrameRow[];
  vocal_phrase: { start_s: number; end_s: number; confidence: number | null }[];
}

export function parseVocalVoiceness(raw: unknown): VocalVoicenessFile {
  const o = asObject(raw, "reference/proposals/vocal_voiceness.json");
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

export async function loadVocalVoiceness(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<VocalVoicenessFile>> {
  const result = await loadJson(artifactPaths.vocalVoiceness(song), parseVocalVoiceness, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return {
      ok: true,
      data: { schema_version: "", song_name: song, interval_ms: 50, frames: [], vocal_phrase: [] },
    };
  }
  return result;
}

// ---------------------------------------------------------------------------
// svdTagger — reference/proposals/svd_tagger.json
// ---------------------------------------------------------------------------
//
// v3.5 item 6: PANNs' `Singing` class head (AudioSet-527, index 27), run on
// BOTH the vocal stem and the mix — the only voiceness candidate (items 4-7)
// that runs more than one producer over the same song. Every frame/phrase
// row carries an explicit `channel: "stem" | "mix"` (see
// `voiceness_common.schema`'s `channel` field and `export.py`'s docstring —
// the "published files are fused from many producers, and say which one
// won" convention, generalised to a proposal file). `interval_ms` is 1000,
// PANNs' own native window grid, reported honestly. Kill condition
// unevaluable until item 1's `type: "vocal"` ground truth exists — and,
// per the plan, this candidate must additionally beat item 4 given its new
// image/pin cost.

export interface SvdTaggerFrameRow extends VoicenessFrameRow {
  channel: "stem" | "mix" | null;
}

export interface SvdTaggerFile {
  schema_version: string;
  song_name: string;
  interval_ms: number;
  frames: SvdTaggerFrameRow[];
  vocal_phrase: { start_s: number; end_s: number; confidence: number | null; channel: "stem" | "mix" | null }[];
}

function parseChannel(v: unknown): "stem" | "mix" | null {
  return v === "stem" || v === "mix" ? v : null;
}

export function parseSvdTagger(raw: unknown): SvdTaggerFile {
  const o = asObject(raw, "reference/proposals/svd_tagger.json");
  const meta = rec(o.metadata);
  const frames = arr(o.frames).map((row): SvdTaggerFrameRow => {
    const r = rec(row);
    return {
      time_s: num(r.time),
      voiceness: num(r.voiceness),
      confidence: r.confidence == null ? null : num(r.confidence),
      channel: parseChannel(r.channel),
    };
  });
  const vocal_phrase = arr(o.vocal_phrase).map((row) => {
    const r = rec(row);
    const start_s = num(r.start);
    return {
      start_s,
      end_s: Math.max(num(r.end, start_s), start_s),
      confidence: r.confidence == null ? null : num(r.confidence),
      channel: parseChannel(r.channel),
    };
  });
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    interval_ms: num(meta.interval_ms, 1000),
    frames,
    vocal_phrase,
  };
}

export async function loadSvdTagger(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<SvdTaggerFile>> {
  const result = await loadJson(artifactPaths.svdTagger(song), parseSvdTagger, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return {
      ok: true,
      data: { schema_version: "", song_name: song, interval_ms: 1000, frames: [], vocal_phrase: [] },
    };
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
// no longer read from `reference/proposals/`). Same shared voiceness shape
// as `vocalVoiceness` — no `channel` field, single producer. `interval_ms`
// is 50, not 1000: VAD spans carry real sub-second onsets/offsets (a
// hysteresis binarizer over the segmentation model's own ~17ms frames), so
// unlike `svdTagger`, this candidate's `vocal_phrase` boundaries are
// genuinely timed, not a 5s clip-window approximation. Diarization was NOT
// attempted (no HF_TOKEN in this environment, and a live-token dependency at
// analysis time is an automatic kill regardless of score) — no diarization
// field exists in this file at all, never a stubbed-out null.

export type WhisperxVadFile = VocalVoicenessFile;

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
// voiceMultiplicity — reference/proposals/voice_multiplicity.json
// ---------------------------------------------------------------------------
//
// Solo vs stacked voice blocks from stereo vocal stem width and L-R correlation.
// Per-song z-scored (absolute width is not comparable across songs). A proposal
// to audition against Human Hints, not ground truth.

export interface VoiceMultiplicityBlock {
  start: number;
  end: number;
  kind: string;
  mean_multiplicity: number | null;
  confidence: number | null;
}

export interface VoiceMultiplicityFile {
  schema_version: string;
  song_name: string;
  blocks: VoiceMultiplicityBlock[];
}

export function parseVoiceMultiplicity(raw: unknown): VoiceMultiplicityFile {
  const o = asObject(raw, "reference/proposals/voice_multiplicity.json");
  const blocks: VoiceMultiplicityBlock[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({
      start: num(r.start),
      end: num(r.end),
      kind: st(r.kind),
      mean_multiplicity: r.mean_multiplicity == null ? null : num(r.mean_multiplicity),
      confidence: r.confidence == null ? null : num(r.confidence),
    });
  }
  blocks.sort((a, b) => a.start - b.start);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function loadVoiceMultiplicity(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<VoiceMultiplicityFile>> {
  const result = await loadJson(
    artifactPaths.voiceMultiplicity(song),
    parseVoiceMultiplicity,
    f,
  );
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}
