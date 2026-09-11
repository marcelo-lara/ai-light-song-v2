import { describe, expect, it } from "vitest";

import humanHints from "../data/__fixtures__/human_hints.json";
import harmonic from "../data/__fixtures__/layer_a_harmonic.json";
import timelineFixture from "../data/__fixtures__/song_event_timeline.json";
import dropProposalsFix from "../data/__fixtures__/drop_proposals.json";
import characterFix from "../data/__fixtures__/character.json";
import vocalFix from "../data/__fixtures__/vocal_transcription.json";

import {
  parseCharacter,
  parseVocalTranscription,
  parseDropProposals,
  parseMoisesLyrics,
} from "../data/sparseArtifacts";
import { parseEventTimeline, parseHarmonicLayer, parseHumanHints } from "../data/parsers";

import {
  arrangementStateContent,
  characterContent,
  vocalTranscriptionContent,
  chordsContent,
  dropProposalsContent,
  gesturesContent,
  humanHintsContent,
  moisesLyricsContent,
  sectionsContent,
  textureNoveltyContent,
  phrasePeriodicityContent,
  structuralVsMicroContent,
  vocalVoicenessContent,
} from "./laneContent";
import type {
  ArrangementStateFile,
  TextureNoveltyFile,
  PhrasePeriodicityFile,
  StructuralVsMicroFile,
  VocalVoicenessFile,
} from "../data/sparseArtifacts";
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
    expect(chordsContent(null)).toEqual([]);
  });
});

describe("dropProposalsContent", () => {
  const blocks = dropProposalsContent(parseDropProposals(dropProposalsFix));

  it("marks a proposal that already matches a human label", () => {
    const matched = blocks.find((b) => b.id === "proposal-002");
    expect(matched?.label).toMatch(/^\u2713 /);
    expect(matched?.caption).toContain("matches human 57.83s");
  });

  it("marks an unconfirmed proposal and names the channels that fired", () => {
    const unconfirmed = blocks.find((b) => b.id === "proposal-001");
    expect(unconfirmed?.label).toBe("? drums_in \u00b7 sub_in \u00b7 voc_out");
    expect(unconfirmed?.caption).toContain("unconfirmed");
    expect(unconfirmed?.summary).toContain("copy it across by hand");
  });

  it("tints a matched proposal differently from an unconfirmed one", () => {
    expect(blocks.find((b) => b.id === "proposal-002")?.tintId).toBe(
      "dropProposalsMatched",
    );
    expect(blocks.find((b) => b.id === "proposal-001")?.tintId).toBeUndefined();
  });

  it("carries the dB evidence in the wide label", () => {
    const matched = blocks.find((b) => b.id === "proposal-002");
    expect(matched?.wideLabel).toContain("vocals_delta -35.3 dB");
    expect(matched?.wideLabel).toContain("bass_reentry +11.9 dB");
  });

  it("is ordered by time and never throws on a missing file", () => {
    expect(blocks.map((b) => b.start_s)).toEqual(
      [...blocks.map((b) => b.start_s)].sort((a, b) => a - b),
    );
    expect(dropProposalsContent(null)).toEqual([]);
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

describe("textureNoveltyContent", () => {
  const file: TextureNoveltyFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 7.15, edge_strength: null },
      { start_s: 7.15, end_s: 29.1, edge_strength: 0.2888 },
    ],
  };
  const blocks = textureNoveltyContent(file);

  it("labels a normal block with its left-edge novelty", () => {
    expect(blocks[1]!.caption).toContain("left-edge novelty 0.29");
    expect(blocks[1]!.wideLabel).toBe("edge 0.29");
  });

  it("renders the first block's null edge honestly", () => {
    expect(blocks[0]!.caption).toContain("first segment (no left edge)");
    expect(blocks[0]!.caption).not.toMatch(/novelty \d/);
  });

  it("never throws on a missing file", () => {
    expect(textureNoveltyContent(null)).toEqual([]);
  });
});

describe("phrasePeriodicityContent", () => {
  const file: PhrasePeriodicityFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 16, title: "Intro", regime: "through-composed", period: null, n_bars: 8 },
      { start_s: 16, end_s: 24, title: "Loop", regime: "bar-loop", period: 1, n_bars: 4 },
    ],
  };
  const blocks = phrasePeriodicityContent(file);

  it("labels a bar-loop block with its period", () => {
    expect(blocks[1]!.wideLabel).toBe("bar-loop");
    expect(blocks[1]!.caption).toContain("repeat unit 1 bar");
  });

  it("renders a null period honestly", () => {
    expect(blocks[0]!.caption).toContain("no phrase structure detected");
    expect(blocks[0]!.caption).not.toMatch(/repeat unit/);
  });

  it("never throws on a missing file", () => {
    expect(phrasePeriodicityContent(null)).toEqual([]);
  });
});

describe("vocalVoicenessContent", () => {
  const file: VocalVoicenessFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    interval_ms: 50,
    frames: [
      { time_s: 0.0, voiceness: 0.05, confidence: 0.9 },
      { time_s: 0.05, voiceness: 0.08, confidence: 0.84 },
      { time_s: 0.1, voiceness: 0.72, confidence: 0.44 },
      { time_s: 0.15, voiceness: 0.81, confidence: 0.62 },
      { time_s: 0.2, voiceness: 0.79, confidence: 0.58 },
    ],
    vocal_phrase: [{ start_s: 0.1, end_s: 0.25, confidence: 0.6 }],
  };
  const blocks = vocalVoicenessContent(file);

  it("merges consecutive same-bucket frames into one run block", () => {
    // frames 0-1 are both "veryLow" (< 0.2) -> one merged run
    const veryLowRun = blocks.find((b) => b.tintId === "vocalVoicenessVeryLow");
    expect(veryLowRun).toBeDefined();
    expect(veryLowRun!.start_s).toBe(0.0);
    expect(veryLowRun!.end_s).toBe(0.1);
    expect(veryLowRun!.detail).toBe("2 frames");
  });

  it("starts a new run when the bucket changes", () => {
    // frame index 2 (0.72, "high") differs from frame index 3/4 ("veryHigh")
    const highRun = blocks.find((b) => b.tintId === "vocalVoicenessHigh");
    expect(highRun).toBeDefined();
    expect(highRun!.start_s).toBe(0.1);
    expect(highRun!.end_s).toBe(0.15);
  });

  it("appends vocal_phrase spans as their own tinted blocks", () => {
    const phraseBlock = blocks.find((b) => b.tintId === "vocalVoicenessPhrase");
    expect(phraseBlock).toBeDefined();
    expect(phraseBlock!.start_s).toBe(0.1);
    expect(phraseBlock!.end_s).toBe(0.25);
    expect(phraseBlock!.wideLabel).toContain("bridged phrase");
  });

  it("never throws on a missing file", () => {
    expect(vocalVoicenessContent(null)).toEqual([]);
  });
});

describe("structuralVsMicroContent", () => {
  const file: StructuralVsMicroFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 16, title: "Intro", kind: "structural", grid_fit_bars: 0.04 },
      { start_s: 16, end_s: 16.6, title: "Pre-drop", kind: "micro", grid_fit_bars: 1.12 },
    ],
  };
  const blocks = structuralVsMicroContent(file);

  it("labels a structural block and prints its grid_fit_bars", () => {
    expect(blocks[0]!.wideLabel).toBe("structural");
    expect(blocks[0]!.caption).toContain("grid fit 0.04 bars");
    expect(blocks[0]!.tintId).toBeUndefined();
  });

  it("gives a micro block the per-block tint override", () => {
    expect(blocks[1]!.wideLabel).toBe("micro");
    expect(blocks[1]!.tintId).toBe("structuralVsMicroMicro");
    expect(blocks[1]!.caption).toContain("micro");
  });

  it("renders a null grid_fit_bars honestly", () => {
    const b = structuralVsMicroContent({
      schema_version: "1.0",
      song_name: "x",
      blocks: [{ start_s: 0, end_s: 1, title: "", kind: "micro", grid_fit_bars: null }],
    });
    expect(b[0]!.caption).toContain("grid fit unknown");
    expect(b[0]!.caption).not.toMatch(/NaN|0\.00 bars/);
  });

  it("never throws on a missing file", () => {
    expect(structuralVsMicroContent(null)).toEqual([]);
  });
});
