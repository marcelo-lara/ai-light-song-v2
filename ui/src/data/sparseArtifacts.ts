// sparseArtifacts.ts — types + tolerant parsers + loaders for the block-lane
// artifacts consumed by item 9's SparseLane (patterns, identifier hints,
// machine / ML events, symbolic phrase windows).
//
// These artifacts are still schema_version "1.0" and their exact shapes vary
// more than the essentia series, so the parsers here are deliberately tolerant:
// they coerce with `Number(x) || 0` / `String(x ?? "")` and never throw on a
// missing optional field. Quality of the structural read comes first, and a
// half-populated artifact should still render its blocks rather than hard-fail
// the whole lane (matches the previous app's `buildTimelineData` behaviour).

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
// patterns — artifacts/layer_d_patterns.json
// ---------------------------------------------------------------------------

export interface PatternOccurrence {
  id: string;
  pattern_id: string;
  label: string;
  occurrence_index: number;
  occurrence_count: number;
  start_s: number;
  end_s: number;
  start_bar: number;
  end_bar: number;
  sequence: string;
  bar_sequence: string;
  mismatch_count: number;
}

export interface PatternsFile {
  schema_version: string;
  song_name: string;
  occurrences: PatternOccurrence[];
}

export function parsePatterns(raw: unknown): PatternsFile {
  const o = asObject(raw, "layer_d_patterns.json");
  const occurrences: PatternOccurrence[] = [];
  for (const p of arr(o.patterns)) {
    const pr = rec(p);
    const list = arr(pr.occurrences);
    const patternId = st(pr.id, "pattern");
    const label = st(pr.label, patternId);
    list.forEach((occ, i) => {
      const or = rec(occ);
      const start_s = num(or.start_s ?? or.start_time ?? or.start);
      const end_s = Math.max(num(or.end_s ?? or.end_time ?? or.end, start_s), start_s);
      occurrences.push({
        id: `${patternId}-${String(i + 1).padStart(3, "0")}`,
        pattern_id: patternId,
        label,
        occurrence_index: i + 1,
        occurrence_count: list.length,
        start_s,
        end_s,
        start_bar: num(or.start_bar),
        end_bar: num(or.end_bar),
        sequence: st(or.sequence ?? pr.sequence),
        bar_sequence: st(or.bar_sequence ?? pr.bar_sequence),
        mismatch_count: num(or.mismatch_count),
      });
    });
  }
  occurrences.sort((a, b) => a.start_s - b.start_s);
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    occurrences,
  };
}

// ---------------------------------------------------------------------------
// generic event rows — energy_summary/hints.json + event_inference/events.*.json
// ---------------------------------------------------------------------------

export interface AnalysisEvent {
  id: string;
  label: string;
  start_s: number;
  end_s: number;
  confidence: number | null;
  intensity: number | null;
  section_id: string | null;
  section_name: string | null;
  created_by: string | null;
  model_name: string | null;
  notes: string;
  evidence_summary: string;
  raw: Record<string, unknown>;
}

function parseEventRow(raw: unknown, i: number, fallbackCreatedBy: string): AnalysisEvent {
  const r = rec(raw);
  const start_s = num(r.start_s ?? r.start_time ?? r.start ?? r.time_s ?? r.time);
  const end_s = Math.max(
    num(r.end_s ?? r.end_time ?? r.end, start_s),
    start_s,
  );
  const notesRaw = r.notes ?? r.summary ?? r.evidence_summary;
  const evidence = rec(r.evidence);
  const explanation = rec(r.explanation);
  const saliency = rec(r.saliency);
  return {
    id: st(r.id ?? r.event_id, `event-${String(i + 1).padStart(3, "0")}`),
    label: st(r.label ?? r.type ?? r.identifier, "event"),
    start_s,
    end_s,
    confidence:
      r.confidence == null ? null : num(r.confidence),
    intensity: r.intensity == null ? null : num(r.intensity),
    section_id: r.section_id == null ? null : st(r.section_id),
    section_name: r.section_name == null ? null : st(r.section_name),
    created_by: st(r.created_by ?? r.model_name, fallbackCreatedBy) || null,
    model_name: r.model_name == null ? null : st(r.model_name),
    notes: Array.isArray(notesRaw) ? notesRaw.join(" ") : st(notesRaw),
    evidence_summary: st(
      explanation.summary ?? saliency.summary ?? evidence.summary,
    ),
    raw: r,
  };
}

export interface EventsFile {
  schema_version: string;
  song_name: string;
  events: AnalysisEvent[];
}

const eventsParser =
  (file: string, fallbackCreatedBy: string) =>
  (raw: unknown): EventsFile => {
    const o = asObject(raw, file);
    const events = arr(o.events)
      .map((e, i) => parseEventRow(e, i, fallbackCreatedBy))
      .sort((a, b) => a.start_s - b.start_s);
    return { schema_version: st(o.schema_version), song_name: st(o.song_name), events };
  };

export const parseIdentifierHints = eventsParser(
  "energy_summary/hints.json",
  "energy_identifier",
);
export const parseMachineEvents = eventsParser(
  "event_inference/events.machine.json",
  "machine",
);
export const parseMlEvents = eventsParser(
  "event_inference/events.ml.json",
  "ml",
);

// ---------------------------------------------------------------------------
// symbolic phrase windows — artifacts/layer_b_symbolic.json (phrase_windows)
// ---------------------------------------------------------------------------

export interface PhraseWindow {
  id: string;
  group_id: string;
  label: string;
  section_id: string | null;
  section_name: string | null;
  start_s: number;
  end_s: number;
  start_bar: number;
  end_bar: number;
  melodic_contour: string | null;
  register_label: string | null;
  raw: Record<string, unknown>;
}

export interface SymbolicPhrasesFile {
  schema_version: string;
  song_name: string;
  phrases: PhraseWindow[];
}

export function parseSymbolicPhrases(raw: unknown): SymbolicPhrasesFile {
  const o = asObject(raw, "layer_b_symbolic.json");
  const groupCounters = new Map<string, number>();
  const phrases = arr(o.phrase_windows).map((w, i): PhraseWindow => {
    const r = rec(w);
    const group = st(r.phrase_group_id ?? r.group_id);
    const n = (groupCounters.get(group) ?? 0) + 1;
    groupCounters.set(group, n);
    const start_s = num(r.start_s ?? r.start_time ?? r.start);
    return {
      id: st(
        r.phrase_window_id ?? r.id,
        group ? `${group}_${n}` : `phrase-${String(i + 1).padStart(3, "0")}`,
      ),
      group_id: group,
      label: group ? `${group} · ${n}` : `Phrase ${i + 1}`,
      section_id: r.section_id == null ? null : st(r.section_id),
      section_name: r.section_name == null ? null : st(r.section_name),
      start_s,
      end_s: Math.max(num(r.end_s ?? r.end_time ?? r.end, start_s), start_s),
      start_bar: num(r.start_bar),
      end_bar: num(r.end_bar),
      melodic_contour: r.melodic_contour == null ? null : st(r.melodic_contour),
      register_label: r.register_label == null ? null : st(r.register_label),
      raw: r,
    };
  });
  phrases.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), phrases };
}

// ---------------------------------------------------------------------------
// drop-impact proposals — reference/proposals/drop_impacts.json
// ---------------------------------------------------------------------------
//
// Candidate `drop impact` instants from the stage-1 proposer in
// `experiments/drop_detection`. They are NOT ground truth: the lane exists so a
// human can audition each candidate against the Human Hints lane and copy the
// survivors across by hand. `matches_human_label` is the proposer's own note
// that a candidate already sits within 0.5 s of a hand-authored impact, so the
// lane can grey out what is already labelled and highlight what is new.

export interface DropProposal {
  id: string;
  start_s: number;
  end_s: number;
  /** which role-change channels fired here, e.g. ["handover", "voc_out"] */
  channels: string[];
  /** time of the human `drop impact` it matches, or null when unconfirmed */
  matches_human_label: number | null;
  evidence: Record<string, number>;
  raw: Record<string, unknown>;
}

export interface DropProposalsFile {
  schema_version: string;
  song_name: string;
  note: string;
  /** every hand-authored `drop impact` instant in this song, for comparison */
  existing_labels: number[];
  proposals: DropProposal[];
}

export function parseDropProposals(raw: unknown): DropProposalsFile {
  const o = asObject(raw, "reference/proposals/drop_impacts.json");
  const proposals = arr(o.proposals).map((row, i): DropProposal => {
    const r = rec(row);
    const start_s = num(r.start_s ?? r.start_time ?? r.start);
    const evidenceIn = rec(r.evidence);
    const evidence: Record<string, number> = {};
    for (const [key, value] of Object.entries(evidenceIn)) {
      const n = Number(value);
      if (Number.isFinite(n)) evidence[key] = n;
    }
    return {
      id: st(r.id, `proposal-${String(i + 1).padStart(3, "0")}`),
      start_s,
      end_s: Math.max(num(r.end_s ?? r.end_time ?? r.end, start_s), start_s),
      channels: arr(r.channels).map((c) => st(c)).filter(Boolean),
      matches_human_label:
        r.matches_human_label == null ? null : num(r.matches_human_label),
      evidence,
      raw: r,
    };
  });
  proposals.sort((a, b) => a.start_s - b.start_s);
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    note: st(o.note),
    existing_labels: arr(o.existing_labels)
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v)),
    proposals,
  };
}

// ---------------------------------------------------------------------------
// allin1 functional structure — reference/proposals/allin1.json
// ---------------------------------------------------------------------------
//
// Named song form from the All-In-One model, exported by `experiments/allin1`.
// Two lanes come out of this one file: the merged sections (what part of the
// song this is) and the transitions between them (where a cue belongs, and
// what kind of change it is). They are proposals — nothing in the pipeline
// reads this file — so both lanes exist to be auditioned against the audio and
// against the shipped Sections lane.
//
// `function_status` is the model's own honesty flag: on songs outside its
// training distribution allin1 emits one or two labels for the whole track, and
// the exporter marks every row `unknown` rather than letting a confident wrong
// name through.

export interface Allin1Section {
  id: string;
  /** Harmonix vocabulary: intro / verse / chorus / bridge / inst / solo / break / outro */
  function: string;
  /** display name — `chorus 2`, or just `bridge` when it occurs once */
  name: string;
  occurrence: number;
  occurrence_count: number;
  start_s: number;
  end_s: number;
  start_bar: number | null;
  bars: number;
  phrase_count: number;
  /** id of the first section carrying the same label, or null when this is it */
  same_label_as: string | null;
  function_status: string;
  raw: Record<string, unknown>;
}

export interface Allin1Transition {
  id: string;
  start_s: number;
  end_s: number;
  time_s: number;
  from: string;
  to: string;
  /** `chorus → inst` */
  pair: string;
  /** lift / release / shift — a reading convention, not a measurement */
  kind: string;
  bar: number | null;
  /** signed distance to the nearest essentia beat, the grid cues snap to */
  essentia_beat_offset_s: number | null;
  on_downbeat: boolean;
  /** time of the hand-placed `drop impact` this matches, or null */
  matches_human_impact: number | null;
  function_status: string;
  raw: Record<string, unknown>;
}

export interface Allin1File {
  schema_version: string;
  song_name: string;
  /** "ok" | "degenerate" | "empty" */
  labelling_status: string;
  labelling_reason: string | null;
  sections: Allin1Section[];
  transitions: Allin1Transition[];
}

export function parseAllin1(raw: unknown): Allin1File {
  const o = asObject(raw, "reference/proposals/allin1.json");
  const labelling = rec(o.labelling);

  const sections = arr(o.sections).map((row, i): Allin1Section => {
    const r = rec(row);
    const start_s = num(r.start_s);
    const fn = st(r.function, "unknown");
    return {
      id: st(r.id, `allin1-${String(i + 1).padStart(3, "0")}`),
      function: fn,
      name: st(r.name, fn),
      occurrence: num(r.occurrence, 1),
      occurrence_count: num(r.occurrence_count, 1),
      start_s,
      end_s: Math.max(num(r.end_s, start_s), start_s),
      start_bar: r.start_bar == null ? null : num(r.start_bar),
      bars: num(r.bars),
      phrase_count: num(r.phrase_count),
      same_label_as: r.same_label_as == null ? null : st(r.same_label_as),
      function_status: st(r.function_status, "named"),
      raw: r,
    };
  });
  sections.sort((a, b) => a.start_s - b.start_s);

  const transitions = arr(o.transitions).map((row, i): Allin1Transition => {
    const r = rec(row);
    const time_s = num(r.time_s ?? r.start_s);
    const start_s = num(r.start_s, time_s);
    return {
      id: st(r.id, `allin1-t-${String(i + 1).padStart(3, "0")}`),
      start_s,
      end_s: Math.max(num(r.end_s, start_s), start_s),
      time_s,
      from: st(r.from, "unknown"),
      to: st(r.to, "unknown"),
      pair: st(r.pair, `${st(r.from)} \u2192 ${st(r.to)}`),
      kind: st(r.kind, "shift"),
      bar: r.bar == null ? null : num(r.bar),
      essentia_beat_offset_s:
        r.essentia_beat_offset_s == null ? null : num(r.essentia_beat_offset_s),
      on_downbeat: r.on_downbeat === true,
      matches_human_impact:
        r.matches_human_impact == null ? null : num(r.matches_human_impact),
      function_status: st(r.function_status, "named"),
      raw: r,
    };
  });
  transitions.sort((a, b) => a.start_s - b.start_s);

  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    labelling_status: st(labelling.status, "unknown"),
    labelling_reason: labelling.reason == null ? null : st(labelling.reason),
    sections,
    transitions,
  };
}

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

export const loadPatterns = (song: string, f?: typeof fetch): Promise<LoadResult<PatternsFile>> =>
  loadJson(artifactPaths.patterns(song), parsePatterns, f);
export const loadIdentifierHints = (song: string, f?: typeof fetch): Promise<LoadResult<EventsFile>> =>
  loadJson(artifactPaths.identifierHints(song), parseIdentifierHints, f);
export const loadMachineEvents = (song: string, f?: typeof fetch): Promise<LoadResult<EventsFile>> =>
  loadJson(artifactPaths.machineEvents(song), parseMachineEvents, f);
export const loadMlEvents = (song: string, f?: typeof fetch): Promise<LoadResult<EventsFile>> =>
  loadJson(artifactPaths.mlEvents(song), parseMlEvents, f);
export const loadSymbolicPhrases = (song: string, f?: typeof fetch): Promise<LoadResult<SymbolicPhrasesFile>> =>
  loadJson(artifactPaths.symbolicLayer(song), parseSymbolicPhrases, f);

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
 * Optional like the drop proposals: it exists only for songs the allin1
 * exporter has been run over, so a 404 resolves to an empty file. Every other
 * failure still surfaces.
 */
export async function loadAllin1(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<Allin1File>> {
  const result = await loadJson(artifactPaths.allin1(song), parseAllin1, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return {
      ok: true,
      data: {
        schema_version: "",
        song_name: song,
        labelling_status: "",
        labelling_reason: null,
        sections: [],
        transitions: [],
      },
    };
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

/**
 * The proposals file is optional — it exists only for songs the drop-detection
 * exporter has been run over — so a 404 resolves to an empty file rather than a
 * load error. Every other failure (network, bad JSON, wrong shape) still
 * surfaces, so a real problem is not silently swallowed.
 */
export async function loadDropProposals(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<DropProposalsFile>> {
  const result = await loadJson(
    artifactPaths.dropProposals(song),
    parseDropProposals,
    f,
  );
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return {
      ok: true,
      data: {
        schema_version: "",
        song_name: song,
        note: "",
        existing_labels: [],
        proposals: [],
      },
    };
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
// reactive-band accents — reference/proposals/reactive_bands.json
// ---------------------------------------------------------------------------
//
// experiments/reactive_bands: discrete accents (instantaneous band-power
// ratio spiking above its own damped twin) from the locally auto-gained FFT
// bands. The dense per-beat/per-bar bass/mid/treb stream this file also
// carries is not rendered as its own lane — see the experiment's README.

export interface ReactiveBandAccent {
  time_s: number;
  band: string;
  strength: number;
  beat: number | null;
  bar: number | null;
}

export interface ReactiveBandsFile {
  schema_version: string;
  song_name: string;
  accents: ReactiveBandAccent[];
}

export function parseReactiveBands(raw: unknown): ReactiveBandsFile {
  const o = asObject(raw, "reference/proposals/reactive_bands.json");
  const accents = arr(o.accents).map((row): ReactiveBandAccent => {
    const r = rec(row);
    return {
      time_s: num(r.time),
      band: st(r.band),
      strength: num(r.strength),
      beat: r.beat == null ? null : num(r.beat),
      bar: r.bar == null ? null : num(r.bar),
    };
  });
  accents.sort((a, b) => a.time_s - b.time_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), accents };
}

export async function loadReactiveBands(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<ReactiveBandsFile>> {
  const result = await loadJson(artifactPaths.reactiveBands(song), parseReactiveBands, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, accents: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// gestures — reference/proposals/gestures.json
// ---------------------------------------------------------------------------
//
// experiments/gestures: composite drop gestures (approach/build/tension/
// impact/release) assembled from named sound-design primitive detectors.
// Never names the section — it says "a build of this shape happens here".

export interface GesturePhase {
  name: string;
  start_s: number;
  end_s: number;
  confidence: number;
  from: string;
}

export interface GestureBlock {
  id: string;
  start_s: number;
  end_s: number;
  impact_time_s: number;
  confidence: number;
  phases: GesturePhase[];
}

export interface GesturesFile {
  schema_version: string;
  song_name: string;
  gestures: GestureBlock[];
}

export function parseGestures(raw: unknown): GesturesFile {
  const o = asObject(raw, "reference/proposals/gestures.json");
  const gestures = arr(o.gestures).map((row, i): GestureBlock => {
    const r = rec(row);
    const phasesIn = rec(r.phases);
    const phases: GesturePhase[] = Object.entries(phasesIn).map(([name, v]) => {
      const pr = rec(v);
      return { name, start_s: num(pr.start), end_s: num(pr.end), confidence: num(pr.confidence), from: st(pr.from) };
    });
    phases.sort((a, b) => a.start_s - b.start_s);
    return {
      id: `gesture-${String(i + 1).padStart(3, "0")}`,
      start_s: num(r.start),
      end_s: num(r.end),
      impact_time_s: num(r.impact_time),
      confidence: num(r.confidence),
      phases,
    };
  });
  gestures.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), gestures };
}

export async function loadGestures(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<GesturesFile>> {
  const result = await loadJson(artifactPaths.gestures(song), parseGestures, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, gestures: [] } };
  }
  return result;
}

// ---------------------------------------------------------------------------
// grid consensus — reference/proposals/grid.json
// ---------------------------------------------------------------------------
//
// experiments/grid_consensus: the resolved downbeat phase + derived phrase
// grid. Only the phrase-grid boundaries are rendered as a lane (a per-beat
// downbeat overlay would be too dense for a block lane); `status` is the
// song-level "resolved" / "unknown" flag from the consensus.

export interface PhraseGridBoundary {
  bar: number;
  time_s: number;
  confidence: number;
}

export interface GridFile {
  schema_version: string;
  song_name: string;
  status: string;
  confidence: number;
  phrase_length_bars: number | null;
  boundaries: PhraseGridBoundary[];
}

export function parseGrid(raw: unknown): GridFile {
  const o = asObject(raw, "reference/proposals/grid.json");
  const phraseGrid = rec(o.phrase_grid);
  const boundaries = arr(phraseGrid.boundaries).map((row): PhraseGridBoundary => {
    const r = rec(row);
    return { bar: num(r.bar), time_s: num(r.time), confidence: num(r.confidence) };
  });
  return {
    schema_version: st(o.schema_version),
    song_name: st(o.song_name),
    status: st(o.status),
    confidence: num(o.confidence),
    phrase_length_bars: phraseGrid.phrase_length_bars == null ? null : num(phraseGrid.phrase_length_bars),
    boundaries,
  };
}

export async function loadGrid(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<GridFile>> {
  const result = await loadJson(artifactPaths.grid(song), parseGrid, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, status: "", confidence: 0, phrase_length_bars: null, boundaries: [] } };
  }
  return result;
}
