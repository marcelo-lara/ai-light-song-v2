export const artifactDefinitions = [
  {
    key: "info",
    label: "Output Info",
    path: (song) => ["data", "output", song, "info.json"],
  },
  {
    key: "beatsOutput",
    label: "Output Beats",
    path: (song) => ["data", "output", song, "beats.json"],
  },
  {
    key: "sectionsOutput",
    label: "Output Sections",
    path: (song) => ["data", "output", song, "sections.json"],
  },
  {
    key: "eventsTimeline",
    label: "Output Event Timeline",
    path: (song) => ["data", "output", song, "song_event_timeline.json"],
  },
  {
    key: "beatsArtifact",
    label: "Artifact Beats",
    path: (song) => ["data", "artifacts", song, "essentia", "beats.json"],
  },
  {
    key: "harmonic",
    label: "Layer A Harmonic",
    path: (song) => ["data", "artifacts", song, "layer_a_harmonic.json"],
  },
  {
    key: "symbolic",
    label: "Layer B Symbolic",
    path: (song) => ["data", "artifacts", song, "layer_b_symbolic.json"],
  },
  {
    key: "energy",
    label: "Layer C Energy",
    path: (song) => ["data", "artifacts", song, "layer_c_energy.json"],
  },
  {
    key: "patterns",
    label: "Layer D Patterns",
    path: (song) => ["data", "artifacts", song, "layer_d_patterns.json"],
  },
  {
    key: "sectionsArtifact",
    label: "Artifact Sections",
    path: (song) => ["data", "artifacts", song, "section_segmentation", "sections.json"],
  },
  {
    key: "drums",
    label: "Drum Events",
    path: (song) => ["data", "artifacts", song, "symbolic_transcription", "drum_events.json"],
  },
  {
    key: "eventFeatures",
    label: "Event Features",
    path: (song) => ["data", "artifacts", song, "event_inference", "features.json"],
  },
  {
    key: "eventIndex",
    label: "Event Timeline Index",
    path: (song) => ["data", "artifacts", song, "event_inference", "timeline_index.json"],
  },
  {
    key: "eventRules",
    label: "Rule Candidates",
    path: (song) => ["data", "artifacts", song, "event_inference", "rule_candidates.json"],
  },
  {
    key: "eventMachine",
    label: "Machine Events",
    path: (song) => ["data", "artifacts", song, "event_inference", "events.machine.json"],
  },
  {
    key: "patternMining",
    label: "Pattern Mining",
    path: (song) => ["data", "artifacts", song, "pattern_mining", "chord_patterns.json"],
  },
  {
    key: "unified",
    label: "Music Feature Layers",
    path: (song) => ["data", "artifacts", song, "music_feature_layers.json"],
  },
  {
    key: "validation",
    label: "Phase 1 Validation",
    path: (song) => ["data", "artifacts", song, "validation", "phase_1_report.json"],
  },
];

export const laneDefinitions = [
  {
    id: "waveform",
    label: "Waveform Anchor",
    description: "Browser-decoded waveform or beat pulse fallback",
    type: "dynamic",
  },
  {
    id: "sections",
    label: "Sections",
    description: "Section windows from artifact-first segmentation",
    type: "sparse",
  },
  {
    id: "phrases",
    label: "Phrase Windows",
    description: "Phrase and repeated-group anchors from the symbolic layer",
    type: "sparse",
  },
  {
    id: "chords",
    label: "Chord Regions",
    description: "Layer A harmonic chord windows",
    type: "sparse",
  },
  {
    id: "patterns",
    label: "Pattern Occurrences",
    description: "Repeated harmonic pattern windows",
    type: "sparse",
  },
  {
    id: "machineEvents",
    label: "Machine Events",
    description: "Rule and machine event windows",
    type: "sparse",
  },
  {
    id: "timelineEvents",
    label: "Export Timeline",
    description: "Output-side helper event projection",
    type: "sparse",
  },
  {
    id: "drums",
    label: "Drum Density",
    description: "Kick, snare, and hat activity from artifact drum events",
    type: "dynamic",
  },
  {
    id: "density",
    label: "Symbolic Density",
    description: "Per-beat note density from the symbolic layer",
    type: "dynamic",
  },
  {
    id: "energy",
    label: "Energy Profile",
    description: "Beat-aligned energy with accent candidates",
    type: "dynamic",
  },
  {
    id: "validation",
    label: "Regression Overlay",
    description: "Beat drift and exported-event comparison overlays",
    type: "dynamic",
  },
];

export const coreArtifactKeys = ["beatsArtifact", "harmonic", "symbolic", "energy", "sectionsArtifact", "eventMachine", "validation"];
export const dynamicLaneIds = new Set(laneDefinitions.filter((lane) => lane.type === "dynamic").map((lane) => lane.id));
export const DEFAULT_ZOOM = 48;
export const MIN_ZOOM = 12;
export const MAX_ZOOM = 180;
export const LABEL_WIDTH = 220;