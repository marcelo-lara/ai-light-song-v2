import { describe, expect, it } from "vitest";

import { ShapeError } from "./parse";
import {
  parseBeats,
  parseBlockEnergy,
  parseBlockReviews,
  parseLyricValidations,
  parseEventTimeline,
  parseFftBands,
  parseHarmonicLayer,
  parseHumanHints,
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
import harmonicFixture from "./__fixtures__/layer_a_harmonic.json";
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

describe("parseHarmonicLayer", () => {
  it("parses the global key", () => {
    const harm = parseHarmonicLayer(harmonicFixture);
    expect(harm.global_key?.source).toBe("reference_promoted");
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

describe("parseBlockEnergy", () => {
  it("reads full and partial ratings joined by hint_id", () => {
    const file = parseBlockEnergy({
      schema_version: "1.0",
      song_name: "_test_song",
      ratings: [
        { hint_id: "hint-001", energy: 5, tension: 4 },
        { hint_id: "hint-002", energy: 3 },
      ],
    });
    expect(file.schema_version).toBe("1.0");
    expect(file.ratings).toEqual([
      { hint_id: "hint-001", energy: 5, tension: 4 },
      { hint_id: "hint-002", energy: 3 },
    ]);
  });

  it("drops out-of-range, non-integer, id-less and fully-empty entries", () => {
    const file = parseBlockEnergy({
      ratings: [
        { hint_id: "a", energy: 9, tension: 2 }, // energy dropped, tension kept
        { hint_id: "b", energy: 3.5 }, // dropped entirely
        { hint_id: "", energy: 4, tension: 4 }, // no id
        { hint_id: "d" }, // no axes
      ],
    });
    expect(file.ratings).toEqual([{ hint_id: "a", tension: 2 }]);
  });

  it("tolerates a missing ratings array (404 -> empty stands in for this)", () => {
    expect(parseBlockEnergy({ song_name: "s" }).ratings).toEqual([]);
  });

  it("throws on a non-object root", () => {
    expect(() => parseBlockEnergy([])).toThrow(ShapeError);
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
