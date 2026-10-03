// laneState.ts — the timeline lane registry + per-session expand/visible state.
//
// Every lane in the previous app's `laneDefinitions` ships (no conductor / tempo / global
// strip — design notes §3). The design's five lanes are expanded by default;
// every other lane starts collapsed. `expanded` and `visible` persist per
// session in localStorage, wrapped in try/catch so a private window or blocked
// storage never breaks the timeline.

import { useCallback, useEffect, useMemo, useState } from "react";

export type LaneKind =
  | "waveform"
  | "fft"
  | "rms"
  | "env"
  | "drums"
  | "validation"
  | "hints"
  | "sections"
  | "proposals"
  | "character"
  | "lyrics"
  | "gestures";

export interface LaneDef {
  id: string;
  label: string;
  /** the small grey sub-caption under the lane label */
  sub: string;
  kind: LaneKind;
  /** body height when expanded (px); collapsed is always 26 */
  height: number;
  /**
   * The `experiments/<name>/` sandbox the lane's `reference/proposals/` file
   * comes from; absent on production (`src/`) lanes. Rendered into the lane
   * head as a quiet flask badge and into the tooltip as
   * `Experiment · experiments/<value> · not promoted to the pipeline` — a
   * human-readable source, not a path to resolve.
   *
   * Experiment lanes: this field and the lanes that carry it leave the
   * registry together when the experiment is promoted into `src/` or abandoned.
   */
  experiment?: string;
}

/**
 * Height (px) of the faint mini data-strip drawn in a collapsed lane body
 * (`drawCollapsedStrip` / SparseLane's tick row). The collapsed row must never
 * be shorter than this or the strip clips (plan item 5).
 */
export const COLLAPSED_STRIP_HEIGHT = 10;

/**
 * Collapsed lane row height (plan item 5 / R1). A collapsed lane shows only its
 * title (no sub-caption) plus the mini strip. 26px fits the single title line
 * and is comfortably ≥ COLLAPSED_STRIP_HEIGHT so the strip is not clipped; the
 * canvas geometry (`drawCollapsedStrip`, SparseLane tick row) is anchored to
 * `rc.height` so it tracks this constant automatically.
 */
export const COLLAPSED_LANE_HEIGHT = 26;

/** The collapsed row height, guaranteed ≥ the mini strip height. */
export function collapsedLaneHeight(): number {
  return Math.max(COLLAPSED_LANE_HEIGHT, COLLAPSED_STRIP_HEIGHT);
}

/** Registry order = top-to-bottom lane order in the timeline. */
export const LANE_DEFS: readonly LaneDef[] = [
  { id: "waveform", label: "Waveform Anchor", sub: "decoded source mix", kind: "waveform", height: 84 },
  { id: "humanHints", label: "Human Hints", sub: "reference/human · human_hints", kind: "hints", height: 58 },
  { id: "llmPendingProposals", label: "LLM Pending Proposals", sub: "reference/proposals · pending.json · unreviewed MCP propose_hint", kind: "proposals", height: 50 },
  { id: "verdictChecks", label: "Verdict Checks", sub: "reference/pre-analysis · verdict.json · hint verdicts + second pass, read-only", kind: "proposals", height: 50 },
  { id: "sections", label: "Sections", sub: "artifact-first segmentation", kind: "sections", height: 50 },
  { id: "humanSections", label: "Human Sections", sub: "reference/human · segments", kind: "hints", height: 58 },
  { id: "moisesSections", label: "Moises Sections", sub: "reference/moises · segments · read-only", kind: "proposals", height: 58 },
  { id: "allin1Sections", label: "allin1 Segmentation", sub: "artifacts/section_segmentation · pre-fusion, read-only", kind: "proposals", height: 58 },
  { id: "moisesLyrics", label: "Moises Lyrics", sub: "reference/moises · per-word tokens · tinted by confidence", kind: "lyrics", height: 84 },
  { id: "arrangementState", label: "Arrangement State", sub: "arrangement_state · who is playing, per-stem RMS state changes", kind: "proposals", height: 58 },
  { id: "vocalPhrases", label: "Vocal Phrases", sub: "experiment · phrase / gap / sustained-note blocks over the vocal stem", kind: "proposals", height: 50, experiment: "vocal_phrases" },
  { id: "allin1Posterior", label: "allin1 Posterior", sub: "experiment · shadow-label spans the published 8-bar argmax discards", kind: "proposals", height: 50, experiment: "allin1_posterior" },
  { id: "stemPresenceSections", label: "Stem Presence Sections", sub: "experiment · bass/drums presence state machine, hysteresis-merged", kind: "proposals", height: 50, experiment: "stem_presence_sections" },
  { id: "vocalCadence", label: "Vocal Cadence", sub: "vocal_cadence.json · lyric-alignment line timing + call events, bar-relative — timing only, no text", kind: "proposals", height: 50 },
  { id: "whisperxVad", label: "Voice phrase (WhisperX VAD)", sub: "speech-domain VAD voiceness + phrase spans with real sub-second onsets (diarization not attempted — no HF_TOKEN)", kind: "proposals", height: 50 },
  { id: "gestures", label: "Gestures", sub: "song_event_timeline · approach/build/tension/impact/release + section transitions", kind: "gestures", height: 58 },
  { id: "filterSweep", label: "Filter Sweeps", sub: "experiment · harmonic/bass stem brightness opening or closing over 2-16 bars at level loudness", kind: "proposals", height: 50, experiment: "filter_sweep" },
  { id: "downbeatReanchor", label: "Downbeat Reanchor", sub: "experiment · bars always 4 beats, relabelled from anchor votes (kick phase, impacts, bass/drums entries); grey = disagreeing or no anchors, confidence null", kind: "proposals", height: 50, experiment: "downbeat_reanchor" },
  { id: "barFeatures", label: "Bar Features", sub: "experiment · one row per bar: loudness, bands, brightness, transients, drum counts, arrangement, sweeps, gestures — tinted by brightness, grey = bar not 4 beats", kind: "proposals", height: 50, experiment: "bar_features" },
  { id: "filterSweepV2", label: "Filter Sweeps v2", sub: "experiment · harmonic stem high/low ratio and rolloff moving over 4-8 bars; the sweep end on the beat grid and what follows (gap / drop / break / none)", kind: "proposals", height: 50, experiment: "filter_sweep_v2" },
  { id: "lightChanges", label: "Light Changes", sub: "experiment · where the light should change (multi-feature change points vs the previous 4-8 bars), role-labelled: groove_in / build / break / drop / gap / fill", kind: "proposals", height: 50, experiment: "light_changes" },
  { id: "phrases", label: "Phrases", sub: "experiment · the song cut where stems enter/leave, impacts, gaps and riser ends land — each edge at a trusted beat, never bar-counted", kind: "proposals", height: 50, experiment: "phrases" },
  { id: "sectionNames", label: "Section Names", sub: "experiment · every phrase named in the typical EDM sequence (Intro, Build-Up, Drop ...) from kick/bass entries and hits; current labels kept where no build→drop unit is found", kind: "proposals", height: 50, experiment: "section_names" },
  { id: "clapEvents", label: "Clap Events", sub: "experiment · claps detected from the drums stem by per-hit spectral shape, never omnizart's label", kind: "proposals", height: 50, experiment: "clap_events" },
  { id: "kickCheck", label: "Kick Check", sub: "experiment · every omnizart kick kept/rejected by spectral shape + percussive-attack gate", kind: "proposals", height: 50, experiment: "kick_check" },
  { id: "kickAttacks", label: "Kick Attacks", sub: "experiment · kick attacks on the mix (steep 40-120 Hz rise + 2-5 kHz click); weaker repeats labelled echo, off-grid ones low confidence", kind: "proposals", height: 50, experiment: "kick_attacks" },
  { id: "crashCheck", label: "Crash Check", sub: "experiment · every omnizart crash kept/rejected by stream-period + decay-shape gate", kind: "proposals", height: 50, experiment: "crash_check" },
  { id: "fftBands", label: "FFT Bands", sub: "essentia · 7 spectral bands", kind: "fft", height: 84 },
  { id: "fftBandsBass", label: "FFT Bands · Bass", sub: "essentia · 7 bands · bass stem (Demucs)", kind: "fft", height: 84 },
  { id: "fftBandsDrums", label: "FFT Bands · Drums", sub: "essentia · 7 bands · drums stem (Demucs)", kind: "fft", height: 84 },
  { id: "fftBandsHarmonic", label: "FFT Bands · Harmonic", sub: "essentia · 7 bands · harmonic stem (Demucs)", kind: "fft", height: 84 },
  { id: "fftBandsVocals", label: "FFT Bands · Vocals", sub: "essentia · 7 bands · vocals stem (Demucs)", kind: "fft", height: 84 },
  { id: "rmsLoudness", label: "RMS Loudness", sub: "essentia · mix + 4 stems", kind: "rms", height: 112 },
  { id: "loudnessEnvelope", label: "Loudness Envelope", sub: "essentia · mix + 4 stems", kind: "env", height: 112 },
  { id: "character", label: "Character", sub: "experiment · what this passage is like", kind: "character", height: 50, experiment: "clap" },
  { id: "vocalTranscription", label: "Vocal Transcription", sub: "experiment · sung lyrics + timing · VocalParse / ACE-Step / whisper", kind: "lyrics", height: 84, experiment: "vocalparse + acestep_transcriber" },
  { id: "drums", label: "Drum Density", sub: "kick / snare / hat / crash activity", kind: "drums", height: 84 },
  { id: "validation", label: "Regression Overlay", sub: "beat drift + event comparison", kind: "validation", height: 84 },
];

/**
 * design notes §2: the lanes expanded on first load, plus the review
 * lane that only exists to be compared against Human Hints while the song
 * plays — Moises Lyrics sits directly under it and opens with it.
 *
 * Experiment lanes leave the registry when promoted or abandoned:
 * `allin1Transitions` went in plan v3.0 item 14 (content now in
 * `song_event_timeline.json`); `arrangementState` was promoted in plan v3.2
 * (it now reads the top-level published `arrangement_state.json` and carries
 * no flask badge). The `drop_detection`, `texture_novelty` and
 * `structural_vs_micro` experiments' lanes were retired (v3.6 item 7) after
 * their v3.6 item 3 archive verdicts — see
 * `docs/archive/experiments_discarded.md`.
 * `allin1Sections` was also removed in v3.0 item 14 on the
 * reasoning that the production `sections` lane already showed its content —
 * that stopped holding once `sections.json` could be overridden outright by
 * a human or moises reference file (docs/reference/analysis.segments.md), so
 * the lane came back as a permanent, non-experiment read-only lane: the
 * fused `sections` lane alone can no longer show what our own segmentation
 * actually produced on a song with a reference override.
 */
export const DEFAULT_EXPANDED: readonly string[] = [
  "waveform",
  "humanHints",
  "humanSections",
  "moisesLyrics",
  "fftBands",
  "rmsLoudness",
  "loudnessEnvelope",
];

export interface LaneFlags {
  expanded: boolean;
  visible: boolean;
}

export type LaneStateMap = Record<string, LaneFlags>;

export interface Lane extends LaneDef, LaneFlags {
  /** rendered body height given the expand flag */
  renderHeight: number;
}

export function defaultLaneState(): LaneStateMap {
  const expanded = new Set(DEFAULT_EXPANDED);
  const out: LaneStateMap = {};
  for (const def of LANE_DEFS) {
    out[def.id] = { expanded: expanded.has(def.id), visible: true };
  }
  return out;
}

const STORAGE_KEY = "als.timeline.laneState.v1";

export function loadLaneState(): LaneStateMap {
  const base = defaultLaneState();
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return base;
    const parsed = JSON.parse(raw) as Partial<Record<string, Partial<LaneFlags>>>;
    for (const def of LANE_DEFS) {
      const saved = parsed?.[def.id];
      if (saved && typeof saved === "object") {
        if (typeof saved.expanded === "boolean") base[def.id]!.expanded = saved.expanded;
        if (typeof saved.visible === "boolean") base[def.id]!.visible = saved.visible;
      }
    }
  } catch {
    // private window / blocked storage / corrupt value — fall back to defaults
  }
  return base;
}

/** Pure "set every lane's `visible` to `value`" — backs showAll / hideAll. */
export function setAllVisible(state: LaneStateMap, value: boolean): LaneStateMap {
  const next: LaneStateMap = {};
  for (const def of LANE_DEFS) {
    next[def.id] = { ...(state[def.id] ?? { expanded: false, visible: true }), visible: value };
  }
  return next;
}

export function saveLaneState(state: LaneStateMap): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore — persistence is a convenience, not a requirement
  }
}

const NO_ABSENT_LANES: ReadonlySet<string> = new Set();

export interface UseLaneStateResult {
  /** every lane, registry order, with its flags + rendered height */
  lanes: Lane[];
  /** only the visible lanes, registry order */
  visibleLanes: Lane[];
  toggleExpanded(id: string): void;
  toggleVisible(id: string): void;
  setExpanded(id: string, expanded: boolean): void;
  setVisible(id: string, visible: boolean): void;
  showAll(): void;
  /** item 8 — hide every lane in one action (persisted like the per-lane toggles) */
  hideAll(): void;
  resetToDefaults(): void;
}

/**
 * `absentLaneIds`: lanes with no source data at all that must not exist for
 * this song — no head, no lane-list row, no empty state (the Verdict Checks
 * lane when the song has no `verdict.json` rows). Distinct from a ready-empty
 * lane, which stays listed but starts hidden.
 */
export function useLaneState(
  absentLaneIds: ReadonlySet<string> = NO_ABSENT_LANES,
): UseLaneStateResult {
  const [state, setState] = useState<LaneStateMap>(loadLaneState);

  useEffect(() => {
    saveLaneState(state);
  }, [state]);

  const mutate = useCallback(
    (id: string, patch: Partial<LaneFlags>) => {
      setState((current) => {
        const prev = current[id];
        if (!prev) return current;
        return { ...current, [id]: { ...prev, ...patch } };
      });
    },
    [],
  );

  const toggleExpanded = useCallback(
    (id: string) => setState((c) => (c[id] ? { ...c, [id]: { ...c[id]!, expanded: !c[id]!.expanded } } : c)),
    [],
  );
  const toggleVisible = useCallback(
    (id: string) => setState((c) => (c[id] ? { ...c, [id]: { ...c[id]!, visible: !c[id]!.visible } } : c)),
    [],
  );
  const setExpanded = useCallback((id: string, expanded: boolean) => mutate(id, { expanded }), [mutate]);
  const setVisible = useCallback((id: string, visible: boolean) => mutate(id, { visible }), [mutate]);
  const showAll = useCallback(() => setState((c) => setAllVisible(c, true)), []);
  const hideAll = useCallback(() => setState((c) => setAllVisible(c, false)), []);
  const resetToDefaults = useCallback(() => setState(defaultLaneState()), []);

  const lanes = useMemo<Lane[]>(
    () =>
      LANE_DEFS.filter((def) => !absentLaneIds.has(def.id)).map((def) => {
        const flags = state[def.id] ?? { expanded: false, visible: true };
        return {
          ...def,
          ...flags,
          renderHeight: flags.expanded ? def.height : COLLAPSED_LANE_HEIGHT,
        };
      }),
    [state, absentLaneIds],
  );

  const visibleLanes = useMemo(() => lanes.filter((lane) => lane.visible), [lanes]);

  return {
    lanes,
    visibleLanes,
    toggleExpanded,
    toggleVisible,
    setExpanded,
    setVisible,
    showAll,
    hideAll,
    resetToDefaults,
  };
}
