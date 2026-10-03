import { describe, expect, it } from "vitest";

import humanHints from "../data/__fixtures__/human_hints.json";
import timelineFixture from "../data/__fixtures__/song_event_timeline.json";
import characterFix from "../data/__fixtures__/character.json";
import vocalFix from "../data/__fixtures__/vocal_transcription.json";

import {
  parseCharacter,
  parseVocalTranscription,
  parseMoisesLyrics,
} from "../data/sparseArtifacts";
import { parseEventTimeline, parseHumanHints, parseHumanSegmentsFile } from "../data/parsers";

import {
  allin1SectionsContent,
  arrangementStateContent,
  characterContent,
  vocalTranscriptionContent,
  gesturesContent,
  humanHintsContent,
  humanSectionsContent,
  llmPendingProposalsContent,
  moisesLyricsContent,
  moisesSectionsContent,
  sectionsContent,
  allin1PosteriorContent,
  stemPresenceSectionsContent,
  vocalCadenceContent,
  clapEventsContent,
  kickCheckContent,
  kickAttacksContent,
  crashCheckContent,
  filterSweepContent,
  barFeaturesContent,
  downbeatReanchorContent,
  filterSweepV2Content,
  lightChangesContent,
  phrasesContent,
  sectionNamesContent,
  verdictChecksContent,
} from "./laneContent";
import type {
  ArrangementStateFile,
  Allin1PosteriorFile,
  StemPresenceSectionsFile,
  VocalCadenceFile,
  ClapEventsFile,
  KickCheckFile,
  KickAttacksFile,
  CrashCheckFile,
  FilterSweepFile,
  BarFeaturesFile,
  DownbeatReanchorFile,
  FilterSweepV2File,
  LightChangesFile,
  PhrasesFile,
  SectionNamesFile,
} from "../data/sparseArtifacts";
import { parseLightChanges } from "../data/sparseArtifacts";
import type { PendingProposalsFile, SectionRow, VerdictFile } from "../data/types";

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

describe("llmPendingProposalsContent", () => {
  const file: PendingProposalsFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    proposals: [
      {
        id: "prop-002",
        status: "pending",
        created_at: "2026-01-02T00:00:00Z",
        rejection_reason: null,
        evidence: "gesture impact at 42.0s with no covering hint",
        type: "hint",
        hint: { start: 40.0, end: 44.0, title: "Strobe on impact", summary: "Impact-aligned strobe." },
      },
      {
        id: "prop-001",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        rejection_reason: null,
        evidence: "chorus energy jump",
        type: "hint",
        hint: { start: 10.0, end: 14.0, title: "Bright wash", summary: "Chorus entry." },
      },
      {
        id: "prop-004",
        status: "approved",
        created_at: "2026-01-01T00:00:00Z",
        rejection_reason: null,
        evidence: "already decided",
        type: "hint",
        hint: { start: 60.0, end: 62.0, title: "Decided hint", summary: "" },
      },
    ],
  };
  const blocks = llmPendingProposalsContent(file);

  it("keeps only pending hint proposals, sorted by start", () => {
    expect(blocks.map((b) => b.reference)).toEqual(["prop-001", "prop-002"]);
  });

  it("maps id/start/end/label/detail/reference from the proposal + its hint", () => {
    const first = blocks[0]!;
    expect(first.id).toBe("llmPendingProposals-prop-001");
    expect(first.start_s).toBe(10.0);
    expect(first.end_s).toBe(14.0);
    expect(first.label).toBe("Bright wash");
    expect(first.detail).toBe("chorus energy jump");
    expect(first.reference).toBe("prop-001");
  });

  it("excludes already-decided proposals", () => {
    expect(blocks.some((b) => b.reference === "prop-004")).toBe(false);
  });

  it("never throws on a missing file", () => {
    expect(llmPendingProposalsContent(null)).toEqual([]);
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

  it("shows the window only, never an energy/tension tag, even for a row that carries them", () => {
    const blocks = humanSectionsContent(parseHumanSegmentsFile([{ start: 0, end: 10, energy: 4, tension: 2 }]));
    expect(blocks[0]!.caption).toBe("0:00.0–0:10.0");
    expect(blocks[0]!.caption).not.toContain("E4");
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

  it("never tints or flags a section as contested, whatever function_status says", () => {
    const blocks = sectionsContent([
      {
        section_id: "section-002",
        start: 3,
        end: 15,
        label: "002 Chorus (0.54)",
        description: "x",
        function: "chorus",
        function_confidence: 0.54,
        function_status: "unknown",
        same_label_as: null,
        confidence: 0.54,
      },
    ]);
    const b = blocks[0]!;
    expect(b.tintId).toBeUndefined();
    expect(b.caption).not.toContain("contested");
    expect(b.raw as Record<string, unknown>).not.toHaveProperty("contested_by");
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
      },
    ]);
    expect(blocks[0]!.tintId).toBeUndefined();
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

describe("allin1PosteriorContent", () => {
  const file: Allin1PosteriorFile = {
    schema_version: "1.0",
    song_name: "Armin - Revolution",
    blocks: [
      { start_s: 144.31, end_s: 155.53, label: "break", mean_share: 0.3226, published_overlap: 0.0 },
      { start_s: 155.57, end_s: 168.16, label: "break", mean_share: 0.32, published_overlap: 0.0 },
    ],
  };
  const blocks = allin1PosteriorContent(file);

  it("labels a shadow-label block with the allin1 label", () => {
    expect(blocks[0]!.label).toBe("break");
    expect(blocks[0]!.wideLabel).toContain("break");
  });

  it("carries published_overlap in the summary rather than hiding it", () => {
    expect(blocks[0]!.summary).toContain("overlap");
  });

  it("never throws on a missing file", () => {
    expect(allin1PosteriorContent(null)).toEqual([]);
  });
});

describe("stemPresenceSectionsContent", () => {
  const file: StemPresenceSectionsFile = {
    schema_version: "1.0",
    song_name: "Rapture - Nadia Ali",
    blocks: [
      {
        start_s: 0.0, end_s: 55.38, bar_start: 1, bar_end: 30,
        state: "stripped", drums_detail: "off", vocals_present_fraction: 0.5,
        confidence: 0.22, boundary_resolved: null,
      },
      {
        start_s: 55.38, end_s: 97.85, bar_start: 31, bar_end: 53,
        state: "full", drums_detail: "full", vocals_present_fraction: 0.1,
        confidence: null, boundary_resolved: false,
      },
    ],
  };
  const blocks = stemPresenceSectionsContent(file);

  it("labels a normal block with its coarse state", () => {
    expect(blocks[0]!.label).toBe("stripped");
    expect(blocks[0]!.caption).toContain("stripped");
  });

  it("renders a null confidence and an unresolved boundary honestly", () => {
    expect(blocks[1]!.summary).toContain("no confidence reported");
    expect(blocks[1]!.summary).toContain("no onset found");
  });

  it("never throws on a missing file", () => {
    expect(stemPresenceSectionsContent(null)).toEqual([]);
  });
});

describe("vocalCadenceContent", () => {
  const file: VocalCadenceFile = {
    schema_version: "1.0",
    song_name: "Queen of Kings - Alessandra",
    source: "human",
    reason: null,
    lines: [
      {
        line_id: 12, start_s: 47.234, end_s: 49.197,
        start_position: { bar: 25, beat: 4, resolved: true },
        end_position: { bar: 26, beat: 1, resolved: true },
        duration_beats: 3.12, token_count: 4, pickup: true,
      },
      {
        line_id: 13, start_s: 49.15, end_s: 50.137,
        start_position: { bar: null, beat: null, resolved: false },
        end_position: { bar: 26, beat: 3, resolved: true },
        duration_beats: null, token_count: 3, pickup: false,
      },
    ],
    calls: [
      { time_s: 99.618, position: { bar: 52, beat: 3, resolved: true } },
    ],
  };
  const blocks = vocalCadenceContent(file);

  it("renders a line block with bar position and token count, never text", () => {
    const line = blocks.find((b) => b.id === "vocal-cadence-line-1")!;
    expect(line.caption).toContain("4 tokens");
    expect(line.caption).toContain("pickup");
    // the fixture's Line dataclass carries no text field at all, so this is
    // a belt-and-braces check against known lyric words from the real song.
    for (const word of ["Queen", "Kings", "wind", "hey"]) {
      expect(line.summary.toLowerCase()).not.toContain(word.toLowerCase());
      expect(line.caption.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });

  it("renders an unresolved bar position honestly, never a guessed bar", () => {
    const line = blocks.find((b) => b.id === "vocal-cadence-line-2")!;
    expect(line.caption).toContain("no bar grid");
  });

  it("renders a call as a distinct, zero-length, textless point marker", () => {
    const call = blocks.find((b) => b.id === "vocal-cadence-call-1")!;
    expect(call.start_s).toBe(call.end_s);
    expect(call.tintId).toBe("vocalCadenceCall");
    expect(call.label).toBe("call");
  });

  it("never throws on a missing file", () => {
    expect(vocalCadenceContent(null)).toEqual([]);
  });
});

describe("clapEventsContent", () => {
  const file: ClapEventsFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    events: [
      { time: 80.144, noise_share: 0.73, body_share: 0.0002, confidence: 0.62 },
      { time: 82.042, noise_share: 0.77, body_share: 0.0, confidence: null },
    ],
  };
  const blocks = clapEventsContent(file);

  it("labels a clap block", () => {
    expect(blocks[0]!.label).toBe("clap");
    expect(blocks[0]!.laneLabel).toBe("Clap Events");
    expect(blocks[0]!.end_s).toBeGreaterThan(blocks[0]!.start_s);
    expect(blocks[0]!.caption).toContain("noise 0.73");
  });

  it("renders a null confidence honestly", () => {
    expect(blocks[1]!.detail).toContain("no confidence reported");
  });

  it("never throws on a missing file", () => {
    expect(clapEventsContent(null)).toEqual([]);
  });
});

describe("kickCheckContent", () => {
  const file: KickCheckFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    kicks: [
      { time: 57.22, verdict: "keep", low_share: 0.98, noise_share: 0.0001 },
      { time: 96.459, verdict: "reject", low_share: 0.89, noise_share: 0.05 },
    ],
  };
  const blocks = kickCheckContent(file);

  it("distinguishes keep vs reject by label and tint", () => {
    expect(blocks[0]!.label).toBe("kick");
    expect(blocks[0]!.tintId).toBe("kickCheckKeep");
    expect(blocks[1]!.label).toBe("reject");
    expect(blocks[1]!.tintId).toBe("kickCheckReject");
  });

  it("never throws on a missing file", () => {
    expect(kickCheckContent(null)).toEqual([]);
  });
});

describe("kickAttacksContent", () => {
  const file: KickAttacksFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    events: [
      { time: 17.363, confidence: 0.74, echo_of: null, on_grid: true, grid: "trusted", rise_db: 27.2, click_db: 18.5, pitch_drop: false },
      { time: 17.691, confidence: 0.2, echo_of: 17.363, on_grid: false, grid: "trusted", rise_db: 8.8, click_db: 7.2, pitch_drop: false },
      { time: 18.01, confidence: 0.26, echo_of: null, on_grid: false, grid: "trusted", rise_db: null, click_db: null, pitch_drop: true },
    ],
  };
  const blocks = kickAttacksContent(file);

  it("labels a kick, tinted on-grid", () => {
    expect(blocks[0]!.label).toBe("kick");
    expect(blocks[0]!.tintId).toBe("kickAttacks");
    expect(blocks[0]!.detail).toBe("rise 27.2 dB · click 18.5 dB");
  });

  it("labels an echo with its parent and tints an off-grid kick apart", () => {
    expect(blocks[1]!.label).toBe("echo");
    expect(blocks[1]!.tintId).toBe("kickAttacksEcho");
    expect(blocks[1]!.wideLabel).toContain("17.36");
    expect(blocks[2]!.tintId).toBe("kickAttacksOffGrid");
    expect(blocks[2]!.caption).toContain("off grid");
  });

  it("renders missing evidence honestly and never throws on a missing file", () => {
    expect(blocks[2]!.detail).toBe("rise n/a dB · click n/a dB · pitch drop");
    expect(kickAttacksContent(null)).toEqual([]);
  });
});

describe("crashCheckContent", () => {
  const file: CrashCheckFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    crashes: [
      { time: 222.37, verdict: "keep", is_stream_continuation: false, decay_ratio: 0.003 },
      { time: 223.33, verdict: "reject", is_stream_continuation: true, decay_ratio: 0.081 },
    ],
  };
  const blocks = crashCheckContent(file);

  it("distinguishes keep vs reject by label and tint", () => {
    expect(blocks[0]!.label).toBe("crash");
    expect(blocks[0]!.tintId).toBe("crashCheckKeep");
    expect(blocks[0]!.wideLabel).toContain("isolated");
    expect(blocks[1]!.label).toBe("reject");
    expect(blocks[1]!.tintId).toBe("crashCheckReject");
    expect(blocks[1]!.wideLabel).toContain("stream member");
  });

  it("renders a missing decay reading honestly", () => {
    const noDecay = crashCheckContent({
      schema_version: "1.0",
      song_name: "_test_song",
      crashes: [{ time: 1.0, verdict: "reject", is_stream_continuation: false, decay_ratio: null }],
    });
    expect(noDecay[0]!.caption).toContain("no decay reading");
  });

  it("never throws on a missing file", () => {
    expect(crashCheckContent(null)).toEqual([]);
  });
});

describe("filterSweepContent", () => {
  const file: FilterSweepFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 0, end_s: 13.9, direction: "opening", stem: "harmonic", depth: 2.12, confidence: 0.74 },
      { start_s: 44.2, end_s: 49.6, direction: "closing", stem: "bass", depth: 1.1, confidence: null },
    ],
  };
  const blocks = filterSweepContent(file);

  it("labels direction and tints opening apart from closing", () => {
    expect(blocks[0]!.label).toBe("opening");
    expect(blocks[0]!.wideLabel).toContain("harmonic");
    expect(blocks[0]!.tintId).toBe("filterSweepOpening");
    expect(blocks[1]!.tintId).toBe("filterSweepClosing");
  });

  it("renders a null confidence honestly", () => {
    expect(blocks[1]!.summary).toContain("no confidence reported");
    expect(blocks[0]!.summary).toContain("confidence 0.74");
  });

  it("never throws on a missing file", () => {
    expect(filterSweepContent(null)).toEqual([]);
  });
});

describe("barFeaturesContent", () => {
  const row = {
    bar: 9, start_s: 15.26, end_s: 16.96, irregular: false, brightness: 0.66,
    transient_density: 0.012, kick_present: true, sweep_state: "opening", light_change_role: "build",
  };
  const file: BarFeaturesFile = {
    schema_version: "3.1",
    song_name: "_test_song",
    bars: [
      row,
      { ...row, bar: 16, start_s: 27.25, end_s: 27.68, irregular: true, brightness: null, kick_present: null,
        sweep_state: null, light_change_role: null },
    ],
  };
  const blocks = barFeaturesContent(file);

  it("labels a bar with its number and kick state", () => {
    expect(blocks[0]!.label).toBe("9");
    expect(blocks[0]!.wideLabel).toContain("kick");
    expect(blocks[0]!.detail).toContain("sweep opening");
    expect(blocks[0]!.detail).toContain("light change: build");
  });

  it("flags a bar that is not 4 beats, and renders null fields honestly", () => {
    expect(blocks[1]!.tintId).toBe("barFeaturesIrregular");
    expect(blocks[1]!.caption).toContain("not 4 beats");
    expect(blocks[1]!.caption).toContain("brightness n/a");
    expect(blocks[1]!.caption).toContain("kick n/a");
  });

  it("never throws on a missing file", () => {
    expect(barFeaturesContent(null)).toEqual([]);
  });
});

describe("filterSweepV2Content", () => {
  const file: FilterSweepV2File = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { start_s: 94.3, end_s: 109.4, direction: "opening", start_bar: 51, end_bar: 59, end_time: 109.39,
        end_kind: "top", aftermath: "gap", hl_change_db: 8.2, roll_change_oct: 1.1, consistency: 0.7, confidence: 0.67 },
      { start_s: 50, end_s: 60, direction: "closing", start_bar: 28, end_bar: null, end_time: 60,
        end_kind: "top", aftermath: "none", hl_change_db: null, roll_change_oct: null, consistency: 0.6, confidence: null },
    ],
  };
  const blocks = filterSweepV2Content(file);

  it("labels a sweep with its aftermath and tints by it", () => {
    expect(blocks[0]!.label).toBe("opening → gap");
    expect(blocks[0]!.tintId).toBe("filterSweepV2Gap");
    expect(blocks[0]!.caption).toContain("end 109.39 s (bar 59)");
  });

  it("renders no aftermath, a null change and no confidence honestly", () => {
    expect(blocks[1]!.label).toBe("closing");
    expect(blocks[1]!.tintId).toBe("filterSweepV2None");
    expect(blocks[1]!.detail).toContain("hl n/a");
    expect(blocks[1]!.summary).toContain("nothing follows: suspect");
    expect(blocks[1]!.summary).toContain("no confidence reported");
    expect(blocks[1]!.caption).toContain("song end");
  });

  it("never throws on a missing file", () => {
    expect(filterSweepV2Content(null)).toEqual([]);
  });
});

describe("lightChangesContent", () => {
  const file: LightChangesFile = parseLightChanges({
    schema_version: "3.1",
    song_name: "_test_song",
    events: [
      { type: "impact", start_time: 1, end_time: 1, confidence: 1, intensity: 1, section_id: null },
      { type: "light_change", role: "mystery", start_time: 27.25, end_time: 27.25, confidence: null, section_id: null },
      { type: "light_change", role: "fill", start_time: 13.54, end_time: 13.54, confidence: null, section_id: "section-001" },
    ],
  });
  const blocks = lightChangesContent(file);

  it("keeps only light_change rows, in time order, labelled with the role and tinted per role", () => {
    expect(blocks.map((b) => b.label)).toEqual(["fill", "mystery"]);
    expect(blocks[0]!.tintId).toBe("lightChangeFill");
    expect(blocks[0]!.start_s).toBe(13.54);
    expect(blocks[0]!.detail).toBe("in section-001");
  });

  it("renders an unknown role, no confidence and no section honestly", () => {
    expect(blocks[1]!.tintId).toBe("lightChangeUnknown");
    expect(blocks[1]!.summary).toContain("no confidence");
    expect(blocks[1]!.detail).toBe("between published sections");
  });

  it("never throws on a missing file", () => {
    expect(lightChangesContent(null)).toEqual([]);
  });
});

describe("phrasesContent", () => {
  const base = {
    n_beats: 32, kick_presence: 0.9, bass_presence: 0.8, vocals_presence: 0.1,
    riser_density: 0.25, snare_roll_density: 0, filter_sweeps: [], noise_sweep: false,
    noise_sweep_strength: 0.05, kick_dropout_near_end: true, ends_on_gap: true,
    repeat_of: null, repeat_distance: null, start_edge: null, end_edge: null,
  };
  const file: PhrasesFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    blocks: [
      { ...base, id: "phrase-01", start_s: 0, end_s: 30, resolved: true, conflicts: [], confidence: 0.8 },
      {
        ...base, id: "phrase-02", start_s: 30, end_s: 60, resolved: false,
        conflicts: ["grid: no trusted beat within one beat of the physical change"],
        confidence: null, kick_presence: null, filter_sweeps: null, kick_dropout_near_end: null,
      },
    ],
  };
  const blocks = phrasesContent(file);

  it("tints an unresolved phrase apart and marks its label", () => {
    expect(blocks[0]!.label).toBe("1");
    expect(blocks[0]!.tintId).toBe("phrases");
    expect(blocks[1]!.label).toBe("2?");
    expect(blocks[1]!.tintId).toBe("phrasesUnresolved");
    expect(blocks[1]!.summary).toContain("UNRESOLVED");
  });

  it("names presence and flags in the wide label", () => {
    expect(blocks[0]!.wideLabel).toContain("kick+bass");
    expect(blocks[0]!.wideLabel).toContain("ends on gap");
  });

  it("renders null fields honestly, never as a default", () => {
    expect(blocks[1]!.summary).toContain("kick n/a");
    expect(blocks[1]!.summary).toContain("filter sweeps n/a");
    expect(blocks[1]!.summary).toContain("no confidence reported");
  });

  it("never throws on a missing file", () => {
    expect(phrasesContent(null)).toEqual([]);
  });
});

describe("sectionNamesContent", () => {
  const row = {
    why: ["kick entry 1.00 + impact 1.00"], unit: "unit-01", phrase_ids: ["phrase-04"],
    inherited_from: null,
  };
  const file: SectionNamesFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    status: "named",
    status_reason: null,
    units: [],
    blocks: [
      { ...row, id: "name-01", start_s: 0, end_s: 30, label: "Intro", confidence: 0.85, start_kind: "song_start", source: "section_names" },
      { ...row, id: "name-02", start_s: 30, end_s: 60, label: "Drop", confidence: null, start_kind: "evidence_unsnapped", source: "section_names", inherited_from: "phrase-02" },
      { ...row, id: "name-03", start_s: 60, end_s: 90, label: "Chorus", confidence: 0.5, start_kind: "kept_current", source: "sections.json", unit: null, phrase_ids: [] },
    ],
  };
  const blocks = sectionNamesContent(file);

  it("labels a normal block with the stage name and its confidence", () => {
    expect(blocks[0]!.label).toBe("Intro");
    expect(blocks[0]!.wideLabel).toBe("Intro · 0.85");
    expect(blocks[0]!.tintId).toBe("sectionNames");
    expect(blocks[0]!.summary).toContain("starts at the song start");
  });

  it("renders null confidence and an unsnapped boundary honestly", () => {
    expect(blocks[1]!.wideLabel).toBe("Drop");
    expect(blocks[1]!.summary).toContain("no confidence reported");
    expect(blocks[1]!.summary).toContain("not snapped");
    expect(blocks[1]!.summary).toContain("inherited from phrase-02");
  });

  it("tints and attributes a kept current label apart", () => {
    expect(blocks[2]!.tintId).toBe("sectionNamesKept");
    expect(blocks[2]!.caption).toContain("kept current label");
    expect(blocks[2]!.summary).toContain("source sections.json");
  });

  it("never throws on a missing file", () => {
    expect(sectionNamesContent(null)).toEqual([]);
  });
});

describe("verdictChecksContent", () => {
  const sec = (id: string, start: number, end: number) =>
    ({ section_id: id, start, end }) as unknown as SectionRow;
  const sections = [sec("s1", 0, 10), sec("s2", 10, 20), sec("s3", 20, 30), sec("s4", 30, 40)];
  const file: VerdictFile = {
    schema_version: "3.1",
    song_name: "s",
    rows: [
      { field: "drops", verdict: "refuted", section_ids: ["s3", "s2"], second_pass: null },
      { field: "chorus_is_drop", verdict: "unresolved", section_ids: ["s4"], second_pass: null },
      { field: "has_build_ups", verdict: "confirmed", section_ids: ["s1"], second_pass: null },
      { field: "bpm", verdict: "confirmed", section_ids: [], second_pass: null },
      { field: "vocals", verdict: "unresolved", section_ids: ["gone"], second_pass: null },
    ],
  };
  const check = (status: "pending" | "approved" | "rejected", reason: string | null = null) =>
    ({
      id: "vc1", type: "verdict_check", status, created_at: "", rejection_reason: reason, evidence: "x",
      verdict_check: { field: "chorus_is_drop" },
    }) as unknown as PendingProposalsFile["proposals"][number];
  const queue = (...proposals: PendingProposalsFile["proposals"]): PendingProposalsFile => ({
    schema_version: "1.0", song_name: "s", proposals,
  });

  it("one block per row with resolvable section evidence, spanning first to last section", () => {
    const blocks = verdictChecksContent(file, sections, null);
    expect(blocks.map((b) => b.id)).toEqual([
      "verdictChecks-has_build_ups", "verdictChecks-drops", "verdictChecks-chorus_is_drop",
    ]);
    const drops = blocks.find((b) => b.label === "drops")!;
    expect([drops.start_s, drops.end_s]).toEqual([10, 30]);
  });

  it("tints by outcome: one tint per outcome", () => {
    const tints = verdictChecksContent(file, sections, null).map((b) => b.tintId);
    expect(new Set(tints)).toEqual(
      new Set(["verdictConfirmed", "verdictRefuted", "verdictUnresolved"]),
    );
  });

  it("a pending verdict_check is exposed to the click handler, nothing else is", () => {
    const blocks = verdictChecksContent(file, sections, queue(check("pending")));
    const raw = (id: string) => blocks.find((b) => b.id === id)!.raw as { pending_check_id: string | null };
    expect(raw("verdictChecks-chorus_is_drop").pending_check_id).toBe("vc1");
    expect(raw("verdictChecks-drops").pending_check_id).toBeNull();
  });

  it("a decided check retints the block and prints the operator answer in the tooltip", () => {
    const blocks = verdictChecksContent(file, sections, queue(check("rejected", "audio disagrees")));
    const b = blocks.find((x) => x.id === "verdictChecks-chorus_is_drop")!;
    expect(b.tintId).toBe("verdictRefuted");
    expect(b.tooltip).toContain("operator: rejected — audio disagrees");
    expect((b.raw as { pending_check_id: string | null }).pending_check_id).toBeNull();
  });

  it("a settled second pass shows its wrong side", () => {
    const f: VerdictFile = {
      ...file,
      rows: [{ field: "drops", verdict: "refuted", section_ids: ["s2"],
        second_pass: { verdict: "refuted", wrong: "hint", operator: null } }],
    };
    const [b] = verdictChecksContent(f, sections, null);
    expect(b!.tooltip).toContain("second pass: refuted (wrong: hint)");
  });

  it("no file, no blocks", () => {
    expect(verdictChecksContent(null, sections, null)).toEqual([]);
  });
});

describe("downbeatReanchorContent", () => {
  const file: DownbeatReanchorFile = {
    schema_version: "1.0",
    song_name: "_test_song",
    bars: [
      { bar: 2, start_s: 2.0, end_s: 4.0, beats_in_bar: 4, irregular: false, resolved: true, downbeat_confidence: 0.9 },
      { bar: 3, start_s: 4.0, end_s: 5.5, beats_in_bar: 3, irregular: true, resolved: false, downbeat_confidence: null },
    ],
  };
  const blocks = downbeatReanchorContent(file);

  it("labels a resolved bar with its number and confidence", () => {
    expect(blocks[0]!.label).toBe("2");
    expect(blocks[0]!.tintId).toBe("downbeatReanchor");
    expect(blocks[0]!.caption).toContain("confidence 0.9");
  });

  it("renders a null confidence honestly, grey", () => {
    expect(blocks[1]!.tintId).toBe("downbeatReanchorUnresolved");
    expect(blocks[1]!.caption).toContain("no confidence (unresolved)");
    expect(blocks[1]!.caption).not.toMatch(/confidence 0/);
  });

  it("never throws on a missing file", () => {
    expect(downbeatReanchorContent(null)).toEqual([]);
  });
});
