import { describe, expect, it } from "vitest";

import humanHints from "../data/__fixtures__/human_hints.json";
import harmonic from "../data/__fixtures__/layer_a_harmonic.json";
import patternsFix from "../data/__fixtures__/layer_d_patterns.json";
import identifiersFix from "../data/__fixtures__/energy_summary_hints.json";
import machineFix from "../data/__fixtures__/events_machine.json";
import mlFix from "../data/__fixtures__/events_ml.json";
import symbolicFix from "../data/__fixtures__/layer_b_symbolic.json";
import dropProposalsFix from "../data/__fixtures__/drop_proposals.json";

import {
  parseDropProposals,
  parseIdentifierHints,
  parseMachineEvents,
  parseMlEvents,
  parsePatterns,
  parseSymbolicPhrases,
} from "../data/sparseArtifacts";
import { parseHarmonicLayer, parseHumanHints } from "../data/parsers";

import {
  chordsContent,
  dropProposalsContent,
  humanHintsContent,
  identifierHintsContent,
  machineEventsContent,
  mlEventsContent,
  patternsContent,
  phrasesContent,
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
  it("labels by form_role when present, else the projection label", () => {
    const blocks = sectionsContent([
      {
        start: 0,
        end: 10,
        label: "001 Ambient Opening (0.66)",
        description: "x",
        hints: [],
        section_id: "section-001",
        form_role: null,
        energy_character: "low",
        repetition_group: null,
        confidence: 0.66,
      },
    ]);
    expect(blocks[0]!.label).toBe("001 Ambient Opening (0.66)");
    expect(blocks[0]!.reference).toBe("section-001");
    expect(blocks[0]!.caption).toContain("conf 0.66");
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

describe("patternsContent", () => {
  it("flattens occurrences and keeps occurrence index/count", () => {
    const blocks = patternsContent(parsePatterns(patternsFix));
    expect(blocks.length).toBe(27);
    expect(blocks[0]!.label).toBe("Pattern A");
    expect(blocks[0]!.reference).toBe("pattern_A");
    expect(blocks[0]!.summary).toContain("Occurrence 1 of 27");
  });
});

describe("identifier / machine / ml event content", () => {
  it("identifierHints keeps the drop identifier", () => {
    const blocks = identifierHintsContent(parseIdentifierHints(identifiersFix));
    expect(blocks).toHaveLength(1);
    expect(blocks[0]!.label).toBe("drop");
    expect(blocks[0]!.laneLabel).toBe("Identifier Hints");
  });

  it("machineEvents surfaces evidence summaries", () => {
    const blocks = machineEventsContent(parseMachineEvents(machineFix));
    expect(blocks.length).toBeGreaterThan(0);
    expect(blocks[0]!.end_s).toBeGreaterThanOrEqual(blocks[0]!.start_s);
    expect(blocks.every((b) => b.laneLabel === "Machine Events")).toBe(true);
  });

  it("mlEvents on an empty artifact yields no blocks", () => {
    expect(mlEventsContent(parseMlEvents(mlFix))).toEqual([]);
  });
});


describe("phrasesContent", () => {
  it("labels phrase windows by group id", () => {
    const blocks = phrasesContent(parseSymbolicPhrases(symbolicFix));
    expect(blocks.length).toBe(6);
    expect(blocks[0]!.label).toContain("phrase_group");
    expect(blocks[0]!.laneLabel).toBe("Symbolic Phrases");
  });
});

describe("null inputs", () => {
  it("every adapter tolerates a missing artifact", () => {
    expect(humanHintsContent(null)).toEqual([]);
    expect(chordsContent(null)).toEqual([]);
    expect(patternsContent(null)).toEqual([]);
    expect(phrasesContent(null)).toEqual([]);
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
