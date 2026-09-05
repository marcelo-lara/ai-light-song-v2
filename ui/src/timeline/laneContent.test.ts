import { describe, expect, it } from "vitest";

import humanHints from "../data/__fixtures__/human_hints.json";
import harmonic from "../data/__fixtures__/layer_a_harmonic.json";
import timelineFixture from "../data/__fixtures__/song_event_timeline.json";
import dropProposalsFix from "../data/__fixtures__/drop_proposals.json";
import allin1Fix from "../data/__fixtures__/allin1.json";
import characterFix from "../data/__fixtures__/character.json";
import vocalFix from "../data/__fixtures__/vocal_transcription.json";

import {
  parseAllin1,
  parseCharacter,
  parseVocalTranscription,
  parseDropProposals,
} from "../data/sparseArtifacts";
import { parseEventTimeline, parseHarmonicLayer, parseHumanHints } from "../data/parsers";

import {
  allin1SectionsContent,
  allin1TransitionsContent,
  characterContent,
  vocalTranscriptionContent,
  chordsContent,
  dropProposalsContent,
  gesturesContent,
  humanHintsContent,
  sectionsContent,
} from "./laneContent";
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

describe("allin1SectionsContent", () => {
  const blocks = allin1SectionsContent(parseAllin1(allin1Fix));

  it("names a returning section by its occurrence", () => {
    expect(blocks.map((b) => b.label)).toContain("chorus 2");
    expect(blocks.map((b) => b.label)).toContain("bridge");
  });

  it("says which earlier section carries the same label", () => {
    const third = blocks.find((b) => b.id === "allin1-009");
    expect(third?.detail).toBe("same label as allin1-003");
    const first = blocks.find((b) => b.id === "allin1-003");
    expect(first?.detail).toBe("1 of 3 chorus sections");
  });

  it("puts the bar span and phrase count in the wide label", () => {
    const inst = blocks.find((b) => b.id === "allin1-004");
    expect(inst?.wideLabel).toContain("bars 40–47");
    expect(inst?.wideLabel).toContain("1 phrase");
  });

  it("marks every row unknown and mutes it when allin1 degenerated", () => {
    const degenerate = allin1SectionsContent(
      parseAllin1({
        ...allin1Fix,
        labelling: { status: "degenerate", reason: "only 2 distinct label(s)" },
      }),
    );
    expect(degenerate[0]!.label).toMatch(/ \?$/);
    expect(degenerate[0]!.tintId).toBe("allin1Unnamed");
    expect(degenerate[0]!.summary).toContain("treat the boundary as the finding");
  });

  it("tolerates a missing file", () => {
    expect(allin1SectionsContent(null)).toEqual([]);
  });
});

describe("allin1TransitionsContent", () => {
  const blocks = allin1TransitionsContent(parseAllin1(allin1Fix));

  it("keeps the destination in the narrow label and the full pair in the wide one", () => {
    const block = blocks.find((b) => b.id === "allin1-t-003");
    expect(block?.label).toBe("? \u2192 inst");
    expect(block?.wideLabel).toContain("chorus \u2192 inst");
  });

  it("marks and tints a transition that already matches a human impact", () => {
    const matched = blocks.find((b) => b.id === "allin1-t-006");
    expect(matched?.label).toMatch(/^\u2713 /);
    expect(matched?.caption).toContain("matches human 151.26s");
    expect(matched?.tintId).toBe("allin1TransitionsMatched");
    expect(blocks.find((b) => b.id === "allin1-t-003")?.tintId).toBeUndefined();
  });

  it("reports the offset to the essentia beat grid cues snap to", () => {
    expect(blocks.find((b) => b.id === "allin1-t-003")?.wideLabel).toMatch(/off beat/);
  });

  it("is ordered by time and tolerates a missing file", () => {
    expect(blocks.map((b) => b.start_s)).toEqual(
      [...blocks.map((b) => b.start_s)].sort((a, b) => a - b),
    );
    expect(allin1TransitionsContent(null)).toEqual([]);
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
