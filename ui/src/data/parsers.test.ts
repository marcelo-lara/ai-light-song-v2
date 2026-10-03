import { describe, expect, it } from "vitest";

import { ShapeError } from "./parse";
import {
  parseBeats,
  parseBlockReviews,
  parseLyricValidations,
  parseEventTimeline,
  parseFftBands,
  parseHumanHints,
  parseHumanSegmentsFile,
  parsePendingProposals,
  parseVerdictFile,
  parseInfo,
  parseLoudnessEnvelope,
  parseReviewQueue,
  parseSongFacts,
  parseRmsLoudness,
  parseSectionSegmentation,
  parseSectionsTopLevelRows,
  parseSectionDisplay,
  mergeSectionDisplay,
} from "./parsers";

import infoFixture from "./__fixtures__/info.json";
import beatsFixture from "./__fixtures__/beats.json";
import sectionsFixture from "./__fixtures__/sections_top_level.json";
import sectionsDisplayFixture from "./__fixtures__/sections_display.json";
import segFixture from "./__fixtures__/section_segmentation.json";
import fftFixture from "./__fixtures__/fft_bands.json";
import rmsFixture from "./__fixtures__/rms_loudness.json";
import envFixture from "./__fixtures__/loudness_envelope.json";
import humanHintsFixture from "./__fixtures__/human_hints.json";
import timelineFixture from "./__fixtures__/song_event_timeline.json";
import reviewQueueFixture from "./__fixtures__/review_queue.json";

describe("parseInfo", () => {
  it("reads the top-level info contract", () => {
    const info = parseInfo(infoFixture);
    expect(info.song_name).toBe("_test_song");
    expect(info.duration).toBeGreaterThan(0);
    expect(info.bpm).toBeGreaterThan(0);
    // v3.1 item 8 removed song_path / artifacts / outputs / debug / generated_from.
    expect(info.field_sources).toEqual({ bpm: "essentia", duration: "essentia" });
  });

  it("throws on a missing required field", () => {
    expect(() => parseInfo({ song_name: "x" })).toThrow(ShapeError);
  });

  it("defaults field_sources to an empty object when absent", () => {
    const info = parseInfo({ song_name: "x", duration: 10 });
    expect(info.field_sources).toEqual({});
  });
});

describe("parseBeats", () => {
  it("maps the compact beat row shape", () => {
    const beats = parseBeats(beatsFixture);
    expect(beats.length).toBeGreaterThan(0);
    const first = beats[0]!;
    expect(first).toMatchObject({
      time: expect.any(Number),
      beat: expect.any(Number),
      bar: expect.any(Number),
      type: expect.any(String),
    });
    expect(first.downbeat_confidence).toBeNull();
  });

  it("rejects a non-array", () => {
    expect(() => parseBeats({})).toThrow(ShapeError);
  });
});

describe("parseSectionsTopLevelRows / parseSectionDisplay / mergeSectionDisplay", () => {
  it("parses the v3.0 allin1 named-segmentation projection, joined with its display fields", () => {
    const topLevel = parseSectionsTopLevelRows(sectionsFixture);
    const display = parseSectionDisplay(sectionsDisplayFixture);
    const sections = mergeSectionDisplay(topLevel, display.sections);
    expect(sections.length).toBe(4);
    expect(sections[0]!.label).toMatch(/^\d{3} /);
    expect(sections[0]!.section_id).toBe("section-001");
    expect(sections[0]!.confidence).toBe(0.9);
  });

  it("carries the exact row shape through: section_id, start, end, label, description, confidence", () => {
    const rawTopLevel = [
      {
        section_id: "section-001",
        start: 0,
        end: 10,
        confidence: 0.9,
      },
    ];
    const rawDisplay = {
      schema_version: "3.6",
      song_name: "_test_song",
      sections: [
        {
          section_id: "section-001",
          label: "001 Intro (0.90)",
          description: "Opening section, 10.0s.",
        },
      ],
    };
    const topLevel = parseSectionsTopLevelRows(rawTopLevel);
    const display = parseSectionDisplay(rawDisplay);
    const [row] = mergeSectionDisplay(topLevel, display.sections);
    expect(row).toMatchObject({
      section_id: "section-001",
      label: "001 Intro (0.90)",
      description: "Opening section, 10.0s.",
      confidence: 0.9,
    });
  });

  it("throws when a top-level section_id has no matching display row", () => {
    const topLevel = parseSectionsTopLevelRows([
      { section_id: "section-999", start: 0, end: 10, confidence: 0.5 },
    ]);
    expect(() => mergeSectionDisplay(topLevel, [])).toThrow(ShapeError);
  });
});

describe("parseSectionSegmentation", () => {
  it("parses the v3.0 per-section function fields", () => {
    const seg = parseSectionSegmentation(segFixture);
    expect(seg.schema_version).toBe("3.0");
    expect(seg.sections[0]!.function).toBe("intro");
    expect(seg.sections[0]!.function_status).toBe("ok");
    expect(seg.sections[0]!.same_label_as).toBeNull();
  });

  it("fails loudly on a duplicate section_id (join key)", () => {
    const dup = {
      ...segFixture,
      sections: [segFixture.sections[0], segFixture.sections[0]],
    };
    expect(() => parseSectionSegmentation(dup)).toThrow(/duplicate section_id/);
  });
});

describe("parseFftBands", () => {
  it("keeps bands and per-frame levels index-aligned", () => {
    const fft = parseFftBands(fftFixture);
    expect(fft.bands.length).toBeGreaterThan(0);
    expect(fft.frames[0]!.levels.length).toBe(fft.bands.length);
    expect(fft.bands[0]!.id).toBe("sub");
  });
});

describe("parseRmsLoudness / parseLoudnessEnvelope", () => {
  it("parses per-source frames for rms", () => {
    const rms = parseRmsLoudness(rmsFixture);
    expect(rms.sources.length).toBeGreaterThan(0);
    expect(rms.frames[0]!.values.length).toBe(rms.sources.length);
    expect(rms.frames[0]!.history).not.toBeNull();
  });

  it("parses the envelope series with the same shape", () => {
    const env = parseLoudnessEnvelope(envFixture);
    expect(env.frames[0]!.normalized_values.length).toBe(env.sources.length);
  });
});

describe("parseHumanHints", () => {
  it("normalises the editable hint store", () => {
    const hints = parseHumanHints(humanHintsFixture);
    expect(hints.song_name).toBe("_test_song");
    expect(hints.human_hints[0]!).toMatchObject({
      id: expect.any(String),
      title: expect.any(String),
      start_time: expect.any(Number),
      end_time: expect.any(Number),
    });
  });

  it("accepts an empty / missing human_hints array", () => {
    expect(parseHumanHints({ song_name: "x" }).human_hints).toEqual([]);
  });

  it("carries captured_from and type through, so they survive a reload", () => {
    const hints = parseHumanHints({
      song_name: "x",
      human_hints: [
        {
          id: "hint-001",
          title: "T",
          start_time: 0,
          end_time: 1,
          captured_from: "allin1 Sections · experiments/allin1",
          type: "review",
        },
      ],
    }).human_hints;
    expect(hints[0]!.captured_from).toBe(
      "allin1 Sections · experiments/allin1",
    );
    expect(hints[0]!.type).toBe("review");
  });

  it("carries a vocal type through, so it survives a reload", () => {
    const hints = parseHumanHints({
      song_name: "x",
      human_hints: [
        {
          id: "hint-001",
          title: "T",
          start_time: 0,
          end_time: 1,
          type: "vocal",
        },
      ],
    }).human_hints;
    expect(hints[0]!.type).toBe("vocal");
  });

  it("omits captured_from and type when absent or unrecognised", () => {
    const hints = parseHumanHints({
      song_name: "x",
      human_hints: [
        { id: "hint-001", title: "T", start_time: 0, end_time: 1, type: "bogus" },
      ],
    }).human_hints;
    expect(hints[0]!).not.toHaveProperty("captured_from");
    expect(hints[0]!).not.toHaveProperty("type");
  });
});

describe("parseEventTimeline", () => {
  it("parses flat gesture-phase and section-transition events", () => {
    const tl = parseEventTimeline(timelineFixture);
    expect(tl.schema_version).toBe("2.0");
    const transition = tl.events.find((e) => e.type.includes("→"));
    const phase = tl.events.find((e) => e.type === "impact");
    expect(transition?.summary).toBeTruthy();
    expect(phase?.evidence_summary).toBeTruthy();
    for (const event of tl.events) {
      expect(event.section_id).toMatch(/^section-/);
    }
  });
});

describe("parseReviewQueue", () => {
  it("parses ranked open questions", () => {
    const rq = parseReviewQueue(reviewQueueFixture);
    expect(rq.questions[0]!.field).toContain("form_role");
    expect(rq.questions[0]!.candidates[0]!.score).toBeGreaterThan(0);
    expect(rq.questions[0]!.evidence_timestamps.length).toBeGreaterThan(0);
  });
});

describe("parseSongFacts", () => {
  it("reads facts keyed by field with provenance", () => {
    const facts = parseSongFacts({
      schema_version: "1.1",
      song_name: "_test_song",
      facts: {
        has_drop: {
          value: true,
          provenance: "human-confirmed",
          confirmed_on: "2026-08-30",
          note: "confirmed",
        },
      },
    });
    expect(facts.facts.has_drop!.value).toBe(true);
    expect(facts.facts.has_drop!.provenance).toBe("human-confirmed");
    expect(facts.facts.has_drop!.note).toBe("confirmed");
  });

  it("tolerates a missing facts object", () => {
    expect(parseSongFacts({ schema_version: "1.1", song_name: "s" }).facts).toEqual(
      {},
    );
  });

  it("throws on a non-object root", () => {
    expect(() => parseSongFacts([])).toThrow(ShapeError);
  });
});

describe("parsePendingProposals", () => {
  it("keeps hint proposals and drops a legacy section_field row", () => {
    const file = parsePendingProposals({
      schema_version: "1.0",
      song_name: "s",
      proposals: [
        {
          id: "h1", type: "hint", status: "pending", created_at: "", evidence: "",
          hint: { start: 1, end: 2, title: "t", summary: "" },
        },
        {
          id: "s1", type: "section_field", status: "pending", created_at: "", evidence: "",
          section_field: { section_id: "section-001", field: "x", value: 1 },
        },
      ],
    });
    expect(file.proposals.map((p) => p.id)).toEqual(["h1"]);
  });
});

const EVIDENCE = {
  stems: { read: "bass entries", showed: "bass enters in section-003" },
  drum_density: { read: "drum_density", showed: "dense from section-003" },
  dropouts: { read: "dropouts", showed: "one dropout before section-003" },
  loudness: { read: "loudness", showed: "p90 in section-003" },
  web_search: { read: "web", showed: "a fan wiki says two drops" },
};

describe("parsePendingProposals — verdict_check", () => {
  const row = (over: Record<string, unknown> = {}) => ({
    id: "vc1", type: "verdict_check", status: "pending", created_at: "", evidence: "why",
    verdict_check: {
      field: "drops", claim: "The hint says two drops", evidence: EVIDENCE,
      cannot_settle: "audio shows one", question: "Are there two drops?",
      ...over,
    },
  });

  it("keeps a complete verdict_check row", () => {
    const file = parsePendingProposals({ proposals: [row()] });
    const p = file.proposals[0]!;
    expect(p.type).toBe("verdict_check");
    if (p.type !== "verdict_check") throw new Error("narrow");
    expect(p.verdict_check.field).toBe("drops");
    expect(Object.keys(p.verdict_check.evidence)).toEqual([
      "stems", "drum_density", "dropouts", "loudness", "web_search",
    ]);
  });

  it("skips a row with a missing evidence kind or question instead of half-drawing it", () => {
    const { web_search: _ignored, ...four } = EVIDENCE;
    const file = parsePendingProposals({
      proposals: [row({ evidence: four }), row({ question: "" }), row()],
    });
    expect(file.proposals).toHaveLength(1);
  });
});

describe("parseVerdictFile", () => {
  const raw = {
    schema_version: "3.1",
    song_name: "s",
    verdicts: {
      fields: {
        drops: { verdict: "refuted", evidence: { drop_section_ids: ["section-002", "section-003"], expected: 2 } },
        chorus_is_drop: { verdict: "unresolved", evidence: { drop_like_chorus_section_ids: ["section-005"], build_up_section_ids: ["section-004", "section-005"] } },
        bpm: { verdict: "confirmed", evidence: { analysed_bpm: 128 } },
        vocals: { verdict: "bogus", evidence: {} },
      },
    },
    second_pass: {
      fields: {
        drops: { verdict: "refuted", wrong: "hint", evidence: null, first_pass_verdict: "refuted", operator: null },
        chorus_is_drop: { operator: { answer: "rejected", reason: "no", check_id: "vc1" } },
      },
    },
  };

  it("collects every *_section_ids evidence key and drops an invalid verdict row", () => {
    const file = parseVerdictFile(raw);
    expect(file.rows.map((r) => r.field)).toEqual(["drops", "chorus_is_drop", "bpm"]);
    expect(file.rows[0]!.section_ids).toEqual(["section-002", "section-003"]);
    expect(file.rows[1]!.section_ids).toEqual(["section-005", "section-004"]);
    expect(file.rows[2]!.section_ids).toEqual([]);
  });

  it("reads a settled second pass and an operator-only entry", () => {
    const [drops, chorus, bpm] = parseVerdictFile(raw).rows;
    expect(drops!.second_pass).toEqual({ verdict: "refuted", wrong: "hint", operator: null });
    expect(chorus!.second_pass).toEqual({
      verdict: null, wrong: null,
      operator: { answer: "rejected", reason: "no", check_id: "vc1" },
    });
    expect(bpm!.second_pass).toBeNull();
  });

  it("a file with no verdicts block has no rows", () => {
    expect(parseVerdictFile({ version_check: {} }).rows).toEqual([]);
  });
});

describe("parseHumanSegmentsFile", () => {
  it("carries keys the editor does not own in `preserved`, verbatim", () => {
    const [a, b] = parseHumanSegmentsFile([
      { start: 0, end: 8, label: "Intro", energy: 2, rhythm: { drums: "half" } },
      { start: 8, end: 16, label: "Drop" },
    ]);
    expect(a!.preserved).toEqual({ energy: 2, rhythm: { drums: "half" } });
    expect(b!.preserved).toBeUndefined();
  });
});

describe("removed shapes", () => {
  it("parses a section row without key or contested_by", () => {
    const [row] = parseSectionsTopLevelRows([
      { section_id: "s1", start: 0, end: 1, function: null, function_confidence: null,
        function_status: "unknown", same_label_as: null, confidence: null },
    ]);
    expect(row).not.toHaveProperty("key");
    expect(row).not.toHaveProperty("contested_by");
  });
});

describe("parseBlockReviews", () => {
  it("reads reviews and rounds start to 3 decimals", () => {
    const file = parseBlockReviews({
      schema_version: "1.0",
      song_name: "s",
      reviews: [
        {
          lane_id: "gestures",
          start: 7.8600001,
          verdict: "correct",
          reason: null,
          note: "",
          reviewed_at: "2026-09-19T14:00:00Z",
        },
        {
          lane_id: "gestures",
          start: 9.288,
          verdict: "wrong",
          reason: "boundary",
          note: "phantom",
          reviewed_at: "2026-09-19T14:01:00Z",
        },
      ],
    });
    expect(file.reviews).toHaveLength(2);
    expect(file.reviews[0]!.start).toBe(7.86);
    expect(file.reviews[1]!.reason).toBe("boundary");
  });

  it("drops a row missing lane_id, start or a valid verdict", () => {
    const file = parseBlockReviews({
      reviews: [
        { start: 1, verdict: "correct" }, // no lane_id
        { lane_id: "gestures", verdict: "correct" }, // no start
        { lane_id: "gestures", start: 1, verdict: "maybe" }, // bad verdict
        { lane_id: "gestures", start: 1, verdict: "correct" }, // kept
      ],
    });
    expect(file.reviews).toHaveLength(1);
  });

  it("drops an out-of-vocabulary reason rather than keeping it (a parse concern, not a validation one)", () => {
    const file = parseBlockReviews({
      reviews: [
        { lane_id: "gestures", start: 1, verdict: "wrong", reason: "nonsense" },
      ],
    });
    expect(file.reviews[0]!.reason).toBeNull();
  });

  it("tolerates a missing reviews array", () => {
    expect(parseBlockReviews({ song_name: "s" }).reviews).toEqual([]);
  });

  it("throws on a non-object root", () => {
    expect(() => parseBlockReviews([])).toThrow(ShapeError);
  });
});

describe("parseLyricValidations", () => {
  it("reads the validated_ids list", () => {
    const file = parseLyricValidations({
      schema_version: "1.0",
      song_name: "s",
      validated_ids: [2, 3, 7],
    });
    expect(file.schema_version).toBe("1.0");
    expect(file.validated_ids).toEqual([2, 3, 7]);
  });

  it("drops non-integer / non-finite ids and collapses duplicates", () => {
    expect(
      parseLyricValidations({ validated_ids: [2, 2, 3.5, "x", null, 4] })
        .validated_ids,
    ).toEqual([2, 4]);
  });

  it("tolerates a missing validated_ids array (404 -> empty stands in)", () => {
    expect(parseLyricValidations({ song_name: "s" }).validated_ids).toEqual([]);
  });

  it("throws on a non-object root", () => {
    expect(() => parseLyricValidations([])).toThrow(ShapeError);
  });
});
