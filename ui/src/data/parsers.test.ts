import { describe, expect, it } from "vitest";

import { ShapeError } from "./parse";
import {
  parseBeats,
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
  parseSectionsTopLevel,
} from "./parsers";

import infoFixture from "./__fixtures__/info.json";
import beatsFixture from "./__fixtures__/beats.json";
import sectionsFixture from "./__fixtures__/sections_top_level.json";
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
    expect(typeof info.artifacts).toBe("object");
    expect(info.outputs).not.toBeNull();
  });

  it("throws on a missing required field", () => {
    expect(() => parseInfo({ song_name: "x" })).toThrow(ShapeError);
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
    expect(["string", "object"]).toContain(typeof first.bass); // string | null
  });

  it("rejects a non-array", () => {
    expect(() => parseBeats({})).toThrow(ShapeError);
  });
});

describe("parseSectionsTopLevel", () => {
  it("tolerates the pre-v1.1 shape (no section_id / form_role)", () => {
    const sections = parseSectionsTopLevel(sectionsFixture);
    expect(sections.length).toBe(4);
    expect(sections[0]!.label).toMatch(/^\d{3} /);
    expect(sections[0]!.section_id).toBeNull();
    expect(sections[0]!.form_role).toBeNull();
    expect(Array.isArray(sections[0]!.hints)).toBe(true);
  });

  it("carries v1.1 fields through when present", () => {
    const raw = [
      {
        start: 0,
        end: 10,
        label: "001 Intro (0.9)",
        section_id: "section-001",
        form_role: "intro",
        energy_character: "ambient_opening",
        repetition_group: "A",
        confidence: 0.9,
      },
    ];
    const [row] = parseSectionsTopLevel(raw);
    expect(row).toMatchObject({
      section_id: "section-001",
      form_role: "intro",
      confidence: 0.9,
    });
  });
});

describe("parseSectionSegmentation", () => {
  it("parses form_family and per-section form_role", () => {
    const seg = parseSectionSegmentation(segFixture);
    expect(seg.schema_version).toBe("1.1");
    expect(seg.form_family?.value).toBe("hybrid");
    expect(seg.sections[0]!.form_role).toBe("intro");
    expect(seg.sections[0]!.repetition_group).toBe("A");
  });

  it("fails loudly on a duplicate section_id (v1.1 B5 join key)", () => {
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
  it("parses chords and the global key", () => {
    const harm = parseHarmonicLayer(harmonicFixture);
    expect(harm.global_key?.source).toBe("reference_promoted");
    expect(harm.chords[0]!.chord).toBe("D#m");
    expect(harm.chords[0]!.end_s).toBeGreaterThan(harm.chords[0]!.time);
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
});

describe("parseEventTimeline", () => {
  it("distinguishes composite gestures with phases from plain events", () => {
    const tl = parseEventTimeline(timelineFixture);
    expect(tl.schema_version).toBe("1.1");
    const composite = tl.events.find((e) => e.composite);
    const plain = tl.events.find((e) => !e.composite);
    expect(composite?.phases?.length).toBeGreaterThan(0);
    expect(composite?.member_event_ids?.length).toBeGreaterThan(0);
    expect(plain?.phases).toBeNull();
    expect(tl.texture_summary[0]!.section_id).toMatch(/^section-/);
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
