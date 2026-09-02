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
