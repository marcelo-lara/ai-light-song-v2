import { describe, expect, it } from "vitest";

import humanHints from "../data/__fixtures__/human_hints.json";
import harmonic from "../data/__fixtures__/layer_a_harmonic.json";
import timelineFixture from "../data/__fixtures__/song_event_timeline.json";
import characterFix from "../data/__fixtures__/character.json";
import vocalFix from "../data/__fixtures__/vocal_transcription.json";

import {
  parseCharacter,
  parseVocalTranscription,
  parseMoisesLyrics,
} from "../data/sparseArtifacts";
import { parseEventTimeline, parseHarmonicLayer, parseHumanHints } from "../data/parsers";

import {
  allin1SectionsContent,
  arrangementStateContent,
  characterContent,
  chordsInferenceContent,
  vocalTranscriptionContent,
  chordsContent,
  gesturesContent,
  humanHintsContent,
  humanSectionsContent,
  moisesLyricsContent,
  moisesSectionsContent,
  sectionsContent,
  rhythmDrumIoiContent,
  rhythmStemAutocorrContent,
  rhythmVocalOnsetsContent,
  energyLevelContent,
  tensionShapeContent,
  segmentSeedsContent,
} from "./laneContent";
import type {
  ArrangementStateFile,
  RhythmDrumIoiFile,
  RhythmStemAutocorrFile,
  RhythmVocalOnsetsFile,
  EnergyLevelFile,
  TensionShapeFile,
} from "../data/sparseArtifacts";
import type { HarmonicLayer, HumanSegmentsSeedFile } from "../data/types";
import { romanNumeral } from "./romanNumeral";

describe("humanHintsContent", () => {
  it("maps every hint to a block carrying id + lighting hint", () => {
    const blocks = humanHintsContent(parseHumanHints(humanHints));
    expect(blocks.length).toBeGreaterThan(0);
    const first = blocks[0]!;
    expect(first.id).toBe("hint-001");
    expect(first.laneLabel).toBe("Human Hints");
    expect(first.end_s).toBeGreaterThan(first.start_s);
    expect(first.caption).toContain("Intense strobe");
  });

  it("leaves a hand-authored (or untyped) hint with no tintId override", () => {
    const blocks = humanHintsContent({
      song_name: "s",
      human_hints: [
        {
          id: "hint-001",
          title: "T",
          start_time: 0,
          end_time: 1,
          summary: "",
          lighting_hint: "",
        },
      ],
    });
    expect(blocks[0]!.tintId).toBeUndefined();
  });

  it("tints a review-type hint distinctly from the lane's default", () => {
    const blocks = humanHintsContent({
      song_name: "s",
      human_hints: [
        {
          id: "hint-001",
          title: "T",
          start_time: 0,
          end_time: 1,
          summary: "",
          lighting_hint: "",
          type: "review",
        },
      ],
    });
    expect(blocks[0]!.tintId).toBe("humanHintsReview");
  });

  it("tints a vocal-type hint distinctly from the lane's default and from review", () => {
    const blocks = humanHintsContent({
      song_name: "s",
      human_hints: [
        {
          id: "hint-001",
          title: "T",
          start_time: 0,
          end_time: 1,
          summary: "",
          lighting_hint: "",
          type: "vocal",
        },
      ],
    });
    expect(blocks[0]!.tintId).toBe("humanHintsVocal");
  });
});

describe("humanSectionsContent", () => {
  it("labels a segment from its human label, falling back to the synthesized id", () => {
    const blocks = humanSectionsContent([
      { start: 0, end: 10, label: "Intro", description: "hand-marked" },
      { start: 10, end: 20 },
    ]);
    expect(blocks[0]!.id).toBe("segment-001");
    expect(blocks[0]!.label).toBe("Intro");
    expect(blocks[0]!.summary).toBe("hand-marked");
    expect(blocks[1]!.label).toBe("segment-002");
    expect(blocks[1]!.summary).toBe("Hand-authored section segmentation.");
  });

  it("never throws on a missing file", () => {
    expect(humanSectionsContent(null)).toEqual([]);
  });
});

describe("moisesSectionsContent", () => {
  it("labels a segment from its moises label, read-only shape identical to Human Sections", () => {
    const blocks = moisesSectionsContent([
      { start: 0, end: 14.82, label: "Intro" },
      { start: 14.82, end: 29.58, label: "Verse" },
    ]);
    expect(blocks[0]!.id).toBe("moises-segment-001");
    expect(blocks[0]!.label).toBe("Intro");
    expect(blocks[0]!.laneLabel).toBe("Moises Sections");
    expect(blocks[1]!.label).toBe("Verse");
  });

  it("renders a missing label as the synthesized id, never a guess", () => {
    const blocks = moisesSectionsContent([{ start: 0, end: 10 }]);
    expect(blocks[0]!.label).toBe("moises-segment-001");
    expect(blocks[0]!.summary).toBe("Moises.ai reference segmentation.");
  });

  it("never throws on a missing file", () => {
    expect(moisesSectionsContent(null)).toEqual([]);
  });
});

describe("allin1SectionsContent", () => {
  it("renders the raw, pre-fusion segmentation independent of any override", () => {
    const blocks = allin1SectionsContent([
      {
        section_id: "section-001",
        start: 0,
        end: 14.81,
        function: "Intro",
        function_confidence: 0.34,
        function_status: "unknown",
        same_label_as: null,
        confidence: 0.9,
      },
    ]);
    expect(blocks[0]!.id).toBe("section-001");
    expect(blocks[0]!.label).toBe("Intro");
    expect(blocks[0]!.laneLabel).toBe("allin1 Segmentation");
    expect(blocks[0]!.caption).toContain("conf 0.9");
    expect(blocks[0]!.detail).toBe("unknown");
  });

  it("renders a null function honestly, never a guessed label", () => {
    const blocks = allin1SectionsContent([
      {
        section_id: "section-002",
        start: 14.81,
        end: 20,
        function: null,
        function_confidence: null,
        function_status: "unknown",
        same_label_as: null,
        confidence: null,
      },
    ]);
    expect(blocks[0]!.label).toBe("-");
    expect(blocks[0]!.caption).not.toContain("conf");
  });

  it("never throws on an empty list", () => {
    expect(allin1SectionsContent([])).toEqual([]);
  });
});

describe("sectionsContent", () => {
  it("renders the projected label as-is, unjoined", () => {
    const blocks = sectionsContent([
      {
        section_id: "section-001",
        start: 0,
        end: 10,
        label: "001 Verse (0.66)",
        description: "x",
        function: "verse",
        function_confidence: 0.66,
        function_status: "known",
        same_label_as: null,
        confidence: 0.66,
        key: null,
        chord_progression: null,
      },
    ]);
    expect(blocks[0]!.label).toBe("001 Verse (0.66)");
    expect(blocks[0]!.reference).toBe("section-001");
    expect(blocks[0]!.caption).toContain("conf 0.66");
    expect(blocks[0]!.detail).toBe("-");
  });

  it("joins the section_segmentation artifact by section_id for the inspector's function detail", () => {
    const blocks = sectionsContent(
      [
        {
          section_id: "section-002",
          start: 10,
          end: 20,
          label: "002 Chorus (0.91)",
          description: "y",
          function: "chorus",
          function_confidence: 0.91,
          function_status: "known",
          same_label_as: null,
          confidence: 0.91,
          key: null,
          chord_progression: null,
        },
      ],
      [
        {
          section_id: "section-002",
          start: 10,
          end: 20,
          function: "chorus",
          function_confidence: 0.91,
          function_status: "ok",
          same_label_as: null,
          confidence: 0.91,
        },
      ],
    );
    const raw = blocks[0]!.raw as Record<string, unknown>;
    expect(raw.function).toBe("chorus");
    expect(raw.function_confidence).toBe(0.91);
    expect(raw.function_status).toBe("ok");
    expect(raw.same_label_as).toBeNull();
  });

  it("gives a contested section the sectionsContested tint and card text", () => {
    const blocks = sectionsContent([
      {
        section_id: "section-002",
        start: 3,
        end: 15,
        label: "002 Chorus (0.54)",
        description: "x",
        function: "chorus",
        function_confidence: 0.54,
        function_status: "contested",
        contested_by: "energy",
        same_label_as: null,
        confidence: 0.54,
        key: null,
        chord_progression: null,
      },
    ]);
    const b = blocks[0]!;
    expect(b.tintId).toBe("sectionsContested");
    expect(b.detail).toBe(
      "function_status: contested · contested_by: energy",
    );
    const raw = b.raw as Record<string, unknown>;
    expect(raw.function).toBe("chorus"); // label kept, not flipped
    expect(raw.function_status).toBe("contested");
    expect(raw.contested_by).toBe("energy");
  });

  it("leaves an uncontested section untinted", () => {
    const blocks = sectionsContent([
      {
        section_id: "section-001",
        start: 0,
        end: 10,
        label: "001 Verse (0.66)",
        description: "x",
        function: "verse",
        function_confidence: 0.66,
        function_status: "known",
        same_label_as: null,
        confidence: 0.66,
        key: null,
        chord_progression: null,
      },
    ]);
    expect(blocks[0]!.tintId).toBeUndefined();
  });
});

describe("chordsContent", () => {
  it("emits chord name + a wide roman-numeral label when key is known", () => {
    const blocks = chordsContent(parseHarmonicLayer(harmonic));
    expect(blocks.length).toBeGreaterThan(0);
    expect(blocks[0]!.label).toBe("D#m");
    // fixture global_key.label is null -> no roman numeral
    expect(blocks[0]!.wideLabel).toBeUndefined();
  });

  it("derives a roman numeral when a key label is available", () => {
    expect(romanNumeral("D#m", "D# minor")).toBe("i");
    expect(romanNumeral("B", "D# minor")).toBe("VI");
    expect(romanNumeral("F#", "D# minor")).toBe("III");
  });
});

describe("chordsInferenceContent", () => {
  const harmonicWithProbabilities: HarmonicLayer = {
    schema_version: "3.1",
    song_name: "_test_song",
    global_key: { label: "D# minor", confidence: 0.76, source: "hpcp" },
    chords: [],
    chord_probabilities: [
      { beat: 1, time: 0.510839, label: "D#m", confidence: 0.778155 },
      { beat: 2, time: 1.044898, label: "D#m", confidence: 0.778155 },
      { beat: 3, time: 1.567347, label: "D#m", confidence: 0.667713 },
    ],
  };

  it("renders per-beat chord inference blocks from chord_probabilities", () => {
    const blocks = chordsInferenceContent(harmonicWithProbabilities);
    expect(blocks.length).toBeGreaterThan(0);
    expect(blocks[0]!.label).toBe("D#m");
    expect(blocks[0]!.laneLabel).toBe("Chords");
    expect(blocks[0]!.end_s).toBeGreaterThan(blocks[0]!.start_s);
  });

  it("uses the next inference time as end_s when available", () => {
    const blocks = chordsInferenceContent(harmonicWithProbabilities);
    expect(blocks[0]!.start_s).toBe(0.510839);
    expect(blocks[0]!.end_s).toBe(1.044898);
  });

  it("never throws on a missing artifact", () => {
    expect(chordsInferenceContent(null)).toEqual([]);
  });
});

describe("gesturesContent", () => {
  it("renders one block per flat gesture-phase / transition event", () => {
    const blocks = gesturesContent(parseEventTimeline(timelineFixture));
    expect(blocks.length).toBeGreaterThan(0);
    expect(blocks.every((b) => b.laneLabel === "Gestures")).toBe(true);
    expect(blocks.every((b) => b.end_s >= b.start_s)).toBe(true);
    const labels = blocks.map((b) => b.label);
    expect(labels.some((l) => l.includes("→"))).toBe(true);
    expect(labels.some((l) => l === "impact")).toBe(true);
    for (const b of blocks) {
      expect(b.summary).toBeTruthy();
    }
  });

  it("tolerates a missing artifact", () => {
    expect(gesturesContent(null)).toEqual([]);
  });
});

describe("null inputs", () => {
  it("every adapter tolerates a missing artifact", () => {
    expect(humanHintsContent(null)).toEqual([]);
    expect(chordsInferenceContent(null)).toEqual([]);
    expect(chordsContent(null)).toEqual([]);
  });
});

describe("arrangementStateContent", () => {
  // The published top-level `arrangement_state.json` shape: blocks carry
  // `margin_db` (dB headroom at the flip) and its `confidence` squash, both
  // null on the leading block.
  const file: ArrangementStateFile = {
    schema_version: "3.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0.0, end_s: 16.0, playing: ["bass", "drums", "harmonic", "vocals"], entered: [], left: [], margin_db: null, confidence: null },
      { start_s: 16.0, end_s: 16.75, playing: ["bass", "harmonic", "vocals"], entered: [], left: ["drums"], margin_db: 16.28, confidence: 0.935 },
    ],
  };
  const blocks = arrangementStateContent(file);

  it("labels a change block with the entered/left tokens and carries the margin", () => {
    const changed = blocks[1]!;
    expect(changed.label).toBe("-drums");
    expect(changed.caption).toContain("bass, harmonic, vocals");
    expect(changed.caption).toContain("margin 16.3dB");
    expect(changed.wideLabel).toContain("-drums");
    expect(changed.wideLabel).toContain("margin 16.3dB");
    expect(changed.summary).toContain("-drums at this block's start.");
    expect(changed.summary).toContain("arrangement_state.json");
  });

  it("renders the leading block honestly, with no change and no invented margin", () => {
    const first = blocks[0]!;
    expect(first.caption).toContain("initial state");
    expect(first.caption).not.toMatch(/margin/);
    expect(first.summary).toContain("the leading span, before the first detected change.");
    expect(first.summary).not.toContain("experiments/");
    expect(first.label).toBe("b+d+h+v");
  });

  it("never throws on a missing file", () => {
    expect(arrangementStateContent(null)).toEqual([]);
  });
});

describe("characterContent", () => {
  const blocks = characterContent(parseCharacter(characterFix));

  it("finds the hand-marked Breath block and needs CLAP to do it", () => {
    // Armin - Revolution hint-006: "Breath", 81.395-96.326,
    // "Vocal - no intense section". This is the block the lane was built for.
    const breath = blocks.filter((b) => b.label === "breath");
    const covering = breath.find((b) => b.start_s < 96.326 && b.end_s > 81.395);
    expect(covering).toBeDefined();
    expect(covering!.detail).toBe("stems+clap");
    expect(covering!.summary).toContain("CLAP's calm/intense axis");
  });

  it("tints by kind so texture reads as colour", () => {
    expect(blocks.find((b) => b.label === "breath")?.tintId).toBe("characterBreath");
    expect(blocks.find((b) => b.label === "void")?.tintId).toBe("characterVoid");
    expect(blocks.find((b) => b.label === "vocal lead")?.tintId).toBe(
      "characterVocalLead",
    );
  });

  it("carries allin1 shadow labels with their own explanation", () => {
    const shadow = blocks.find((b) => b.label.startsWith("shadow "));
    expect(shadow?.detail).toBe("allin1");
    expect(shadow?.tintId).toBe("characterShadow");
    expect(shadow?.summary).toContain("its own published segmentation never used");
  });

  it("puts the evidence in the wide label", () => {
    const breath = blocks.find((b) => b.label === "breath");
    expect(breath?.wideLabel).toContain("calm");
    expect(breath?.wideLabel).toContain("stems+clap");
  });

  it("is ordered by time and tolerates a missing file", () => {
    expect(blocks.map((b) => b.start_s)).toEqual(
      [...blocks.map((b) => b.start_s)].sort((a, b) => a - b),
    );
    expect(characterContent(null)).toEqual([]);
  });
});

describe("vocalTranscriptionContent", () => {
  const blocks = vocalTranscriptionContent(parseVocalTranscription(vocalFix));

  it("emits a block per lyric line across every source", () => {
    const texts = blocks.filter((b) => b.detail !== "whisper-large-v3 structure");
    expect(texts.length).toBeGreaterThanOrEqual(5);
    expect(blocks.some((b) => b.detail.startsWith("whisper"))).toBe(true);
    expect(blocks.some((b) => b.detail.startsWith("ACE-Step"))).toBe(true);
    expect(blocks.some((b) => b.detail.startsWith("VocalParse"))).toBe(true);
  });

  it("tints the baseline apart from the models under test", () => {
    const wh = blocks.find((b) => b.detail.startsWith("whisper"));
    const ace = blocks.find((b) => b.detail.startsWith("ACE-Step") && !b.detail.includes("structure"));
    expect(wh?.tintId).toBe("vocalTranscriptionBaseline");
    expect(ace?.tintId).toBe("vocalTranscriptionModel");
  });

  it("says how each block's timing was arrived at and never hides an approximation", () => {
    const aligned = blocks.find((b) => b.detail.startsWith("ACE-Step") && b.summary.includes("Hold your breath"));
    expect(aligned?.summary).toContain("aligned to whisper words");
    const vp = blocks.find((b) => b.detail.startsWith("VocalParse"));
    expect(vp?.summary).toMatch(/approximate|whole-span/);
  });

  it("carries ACE-Step section tags as their own spans", () => {
    const struct = blocks.find((b) => b.reference === "aces001");
    expect(struct?.label).toBe("Verse 1");
    expect(struct?.tintId).toBe("vocalTranscriptionStructure");
  });

  it("is ordered by time and tolerates a missing file", () => {
    expect(blocks.map((b) => b.start_s)).toEqual(
      [...blocks.map((b) => b.start_s)].sort((a, b) => a - b),
    );
    expect(vocalTranscriptionContent(null)).toEqual([]);
  });
});

describe("moisesLyricsContent — v3.4 item 5 validation overlay", () => {
  const file = parseMoisesLyrics([
    { id: 1, line_id: 1, start: 1.0, end: 1.0, text: "<SOL>", confidence: null },
    { id: 2, line_id: 1, start: 1.0, end: 1.2, text: "We", confidence: "0.23" },
    { id: 3, line_id: 1, start: 1.2, end: 1.4, text: "are", confidence: "0.81" },
  ]);

  it("word tokens are validatable and carry their numeric id; markers are not", () => {
    const [sol, we] = moisesLyricsContent(file);
    expect(sol!.lyricValidatable).toBeUndefined();
    expect(sol!.lyricTokenId).toBeUndefined();
    expect(we!.lyricValidatable).toBe(true);
    expect(we!.lyricTokenId).toBe(2);
  });

  it("substitutes confidence 1 + the validated tint for a listed id, source untouched", () => {
    const blocks = moisesLyricsContent(file, new Set([2, 3]));
    const we = blocks.find((b) => b.lyricTokenId === 2)!;
    const are = blocks.find((b) => b.lyricTokenId === 3)!;
    expect(we.tintId).toBe("moisesLyricsValidated");
    expect(we.caption).toContain("conf 1.00");
    expect(we.caption).toContain("human-validated");
    // an id-3 token would normally be the ≥0.7 "High" bucket — validation wins.
    expect(are.tintId).toBe("moisesLyricsValidated");
  });

  it("leaves an unlisted token on its Moises confidence bucket", () => {
    const blocks = moisesLyricsContent(file, new Set([2]));
    const are = blocks.find((b) => b.lyricTokenId === 3)!;
    expect(are.tintId).toBe("moisesLyricsHigh");
  });
});

describe("rhythmDrumIoiContent", () => {
  const file: RhythmDrumIoiFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 8, subdivisions: { drums: "eighth" }, confidence: { drums: 0.62 }, onsets_per_bar: 5.3 },
      { start_s: 8, end_s: 16, subdivisions: { drums: "none" }, confidence: { drums: 0.9 }, onsets_per_bar: 0.4 },
    ],
  };
  const blocks = rhythmDrumIoiContent(file);

  it("labels a normal block with its subdivision and rate", () => {
    expect(blocks[0]!.wideLabel).toContain("drums:eighth");
    expect(blocks[0]!.caption).toContain("5.30/bar");
  });

  it("renders a none block honestly", () => {
    expect(blocks[1]!.wideLabel).toContain("drums:none");
  });

  it("never throws on a missing file", () => {
    expect(rhythmDrumIoiContent(null)).toEqual([]);
  });
});

describe("rhythmStemAutocorrContent", () => {
  const file: RhythmStemAutocorrFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      {
        start_s: 0,
        end_s: 8,
        subdivisions: { drums: "sixteenth", bass: "quarter", vocals: "none" },
        confidence: { drums: 0.5, bass: 0.3, vocals: 1.0 },
      },
    ],
  };
  const blocks = rhythmStemAutocorrContent(file);

  it("lists every source's subdivision", () => {
    expect(blocks[0]!.caption).toContain("drums:sixteenth");
    expect(blocks[0]!.caption).toContain("bass:quarter");
    expect(blocks[0]!.caption).toContain("vocals:none");
  });

  it("never throws on a missing file", () => {
    expect(rhythmStemAutocorrContent(null)).toEqual([]);
  });
});

describe("rhythmVocalOnsetsContent", () => {
  const file: RhythmVocalOnsetsFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 8, subdivisions: { vocals: "eighth" }, confidence: { vocals: 0.4 }, onsets_per_beat: 1.8 },
      { start_s: 8, end_s: 16, subdivisions: { vocals: "none" }, confidence: { vocals: 0.7 }, onsets_per_beat: null },
    ],
  };
  const blocks = rhythmVocalOnsetsContent(file);

  it("labels a normal block with its onset rate", () => {
    expect(blocks[0]!.caption).toContain("1.80/beat");
  });

  it("renders a null onsets_per_beat honestly", () => {
    expect(blocks[1]!.caption).toContain("no onsets");
    expect(blocks[1]!.caption).not.toMatch(/NaN/);
  });

  it("never throws on a missing file", () => {
    expect(rhythmVocalOnsetsContent(null)).toEqual([]);
  });
});

describe("energyLevelContent", () => {
  const file: EnergyLevelFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 8, energy: 4, confidence: 0.72, evidence: { mix_mean: 0.55, stems_fraction: 0.9 } },
    ],
  };
  const blocks = energyLevelContent(file);

  it("labels the energy level and confidence", () => {
    expect(blocks[0]!.wideLabel).toBe("energy 4");
    expect(blocks[0]!.caption).toContain("confidence 0.72");
  });

  it("never throws on a missing file", () => {
    expect(energyLevelContent(null)).toEqual([]);
  });
});

describe("tensionShapeContent", () => {
  const file: TensionShapeFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      {
        start_s: 0,
        end_s: 8,
        tension: 5,
        confidence: 0.3,
        evidence: { slope: 0.12, gesture_bump: true, phrase_periodicity_through_composed_bump: false },
      },
      {
        start_s: 8,
        end_s: 16,
        tension: 2,
        confidence: 0.61,
        evidence: { slope: -0.05, gesture_bump: false, phrase_periodicity_through_composed_bump: false },
      },
    ],
  };
  const blocks = tensionShapeContent(file);

  it("labels the tension level and which bump fired", () => {
    expect(blocks[0]!.wideLabel).toBe("tension 5");
    expect(blocks[0]!.caption).toContain("+gesture");
  });

  it("renders no bump honestly", () => {
    expect(blocks[1]!.caption).toContain("no bump");
  });

  it("never throws on a missing file", () => {
    expect(tensionShapeContent(null)).toEqual([]);
  });
});

describe("segmentSeedsContent", () => {
  const file: HumanSegmentsSeedFile = [
    {
      start: 0,
      end: 16,
      label: "verse",
      energy: 3,
      tension: 2,
      rhythm: { drums: "steady", bass: "root-fifth", harmonic: "sustained", vocals: "syllabic" },
    },
    {
      start: 16,
      end: 32,
      label: null,
      energy: null,
      tension: 4,
      rhythm: { harmonic: "arpeggiated" },
    },
  ];
  const blocks = segmentSeedsContent(file);

  it("labels a fully-seeded row with id, caption tags, and per-source rhythm detail", () => {
    expect(blocks[0]!.id).toBe("segment-seed-001");
    expect(blocks[0]!.laneLabel).toBe("Segment Seeds");
    expect(blocks[0]!.label).toBe("verse");
    expect(blocks[0]!.caption).toContain("E3");
    expect(blocks[0]!.caption).toContain("T2");
    expect(blocks[0]!.detail).toContain("rhythm drums: steady");
    expect(blocks[0]!.summary).toContain("experiments/segment_seeds");
  });

  it("renders a missing energy/label and an unreported rhythm source honestly, never a default", () => {
    expect(blocks[1]!.label).toBe("segment-seed-002");
    expect(blocks[1]!.caption).not.toContain("E");
    expect(blocks[1]!.detail).toContain("energy: not seeded");
    expect(blocks[1]!.detail).toContain("rhythm drums: none reported");
    expect(blocks[1]!.detail).toContain("rhythm harmonic: arpeggiated");
  });

  it("never throws on a missing file", () => {
    expect(segmentSeedsContent(null)).toEqual([]);
  });
});
