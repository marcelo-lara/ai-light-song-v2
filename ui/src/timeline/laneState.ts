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
  | "energy"
  | "validation"
  | "hints"
  | "sections"
  | "chords"
  | "identifiers"
  | "machine"
  | "proposals"
  | "allin1"
  | "character"
  | "lyrics"
  | "gestures"
  | "gridPhrase";

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
   * constitution §3.2: this field and the lanes that carry it leave the
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
  { id: "moisesLyrics", label: "Moises Lyrics", sub: "reference/moises · per-word tokens · tinted by confidence", kind: "lyrics", height: 84 },
  { id: "dropProposals", label: "Drop Proposals", sub: "stage-1 candidates · audition vs. Human Hints", kind: "proposals", height: 58, experiment: "drop_detection" },
  { id: "vocalPhrases", label: "Vocal Phrases", sub: "experiment · phrase / gap / sustained-note blocks over the vocal stem", kind: "proposals", height: 58, experiment: "vocal_phrases" },
  { id: "reactiveBands", label: "Reactive Bands", sub: "experiment · locally auto-gained band-power accents", kind: "proposals", height: 58, experiment: "reactive_bands" },
  { id: "gestures", label: "Gestures", sub: "experiment · approach/build/tension/impact/release", kind: "gestures", height: 58, experiment: "gestures" },
  { id: "gridPhrase", label: "Phrase Grid", sub: "experiment · resolved downbeat phase · 8/16-bar edges", kind: "gridPhrase", height: 58, experiment: "grid_consensus" },
  { id: "allin1Transitions", label: "allin1 Transitions", sub: "experiment · section changes · audition vs. Human Hints", kind: "allin1", height: 58, experiment: "allin1" },
  { id: "fftBands", label: "FFT Bands", sub: "essentia · 7 spectral bands", kind: "fft", height: 84 },
  { id: "rmsLoudness", label: "RMS Loudness", sub: "essentia · mix + 4 stems", kind: "rms", height: 112 },
  { id: "loudnessEnvelope", label: "Loudness Envelope", sub: "essentia · mix + 4 stems", kind: "env", height: 112 },
  { id: "sections", label: "Sections", sub: "artifact-first segmentation", kind: "sections", height: 84 },
  { id: "character", label: "Character", sub: "experiment · what this passage is like", kind: "character", height: 84, experiment: "clap" },
  { id: "vocalTranscription", label: "Vocal Transcription", sub: "experiment · sung lyrics + timing · VocalParse / ACE-Step / whisper", kind: "lyrics", height: 84, experiment: "vocalparse + acestep_transcriber" },
  { id: "allin1Sections", label: "allin1 Sections", sub: "experiment · named song form · compare with Sections", kind: "allin1", height: 84, experiment: "allin1" },
  { id: "chords", label: "Chord Regions", sub: "layer A harmonic", kind: "chords", height: 84 },
  { id: "identifierHints", label: "Identifier Hints", sub: "energy_summary · named events", kind: "identifiers", height: 84 },
  { id: "machineEvents", label: "Machine Events", sub: "rule + machine event windows", kind: "machine", height: 84 },
  { id: "drums", label: "Drum Density", sub: "kick / snare / hat activity", kind: "drums", height: 84 },
  { id: "energy", label: "Energy Profile", sub: "beat-aligned energy + accents", kind: "energy", height: 84 },
  { id: "validation", label: "Regression Overlay", sub: "beat drift + event comparison", kind: "validation", height: 84 },
];

/**
 * design notes §2: the five lanes expanded on first load, plus the two review
 * lanes that only exist to be compared against Human Hints while the song
 * plays — Moises Lyrics, Drop Proposals and allin1 Transitions all sit directly
 * under it and open with it.
 *
 * `allin1Sections` is deliberately NOT here even though it is the headline of
 * the experiment: it belongs next to `sections`, the incumbent it is scored
 * against, and expanding that pair on load pushes the default view past the
 * fold. Expand them together when comparing. The experiment lanes come out of
 * the registry entirely when it is promoted or abandoned (constitution §3.2).
 */
export const DEFAULT_EXPANDED: readonly string[] = [
  "waveform",
  "humanHints",
  "moisesLyrics",
  "dropProposals",
  "allin1Transitions",
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

export function useLaneState(): UseLaneStateResult {
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
      LANE_DEFS.map((def) => {
        const flags = state[def.id] ?? { expanded: false, visible: true };
        return {
          ...def,
          ...flags,
          renderHeight: flags.expanded ? def.height : COLLAPSED_LANE_HEIGHT,
        };
      }),
    [state],
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
