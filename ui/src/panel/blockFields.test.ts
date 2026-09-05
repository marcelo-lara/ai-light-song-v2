import { describe, expect, it } from "vitest";

import type { LaneMarker } from "../timeline/laneRenderers";
import type { SectionRow } from "../data/types";

import {
  blockFields,
  formatRange,
  selectionFromMarker,
  selectionFromSection,
} from "./blockFields";

const val = (fields: { label: string; value: string }[], label: string) =>
  fields.find((f) => f.label === label)?.value;

describe("formatRange", () => {
  it("formats m:ss.s–m:ss.s", () => {
    expect(formatRange(61.5, 78)).toBe("1:01.5–1:18.0");
  });
  it("drops the range when end is null", () => {
    expect(formatRange(5, null)).toBe("0:05.0");
  });
});

describe("selectionFromSection", () => {
  const section: SectionRow = {
    section_id: "S3",
    start: 12,
    end: 30,
    label: "003 Chorus (0.80)",
    description: "energy rises into the chorus",
    confidence: 0.8,
  };
  const block = { section } as { section: SectionRow };

  it("normalises name, window, confidence, reference from the projected label", () => {
    const sel = selectionFromSection(block, "segments");
    expect(sel.label).toBe("Chorus");
    expect(sel.start_s).toBe(12);
    expect(sel.end_s).toBe(30);
    expect(sel.confidence).toBe(0.8);
    expect(sel.reference).toBe("S3");
    expect(sel.summary).toBe("energy rises into the chorus");
  });
});

describe("blockFields — segments / sections", () => {
  it("emits the shared rows in buildSelectionFields order (plain SectionRow, no join)", () => {
    const sel = selectionFromSection(
      {
        section: {
          section_id: "S3",
          start: 12,
          end: 30,
          label: "003 Chorus (0.81)",
          description: null,
          confidence: 0.812,
        },
      } as { section: SectionRow },
      "segments",
    );
    const fields = blockFields("segments", sel);
    expect(fields[0]).toEqual({ label: "Lane", value: "Segments" });
    expect(val(fields, "Window")).toBe("0:12.0–0:30.0");
    expect(val(fields, "Confidence")).toBe("0.81");
    expect(val(fields, "Reference")).toBe("S3");
    expect(val(fields, "Section")).toBe("S3");
  });

  it("V7.3: shows the joined allin1 function detail by exact field name, never section_character/repetition_group", () => {
    // The Sections sparse lane joins `artifacts/section_segmentation/sections.json`
    // onto the block's raw payload by section_id (laneContent.ts sectionsContent).
    const sel = {
      laneId: "sections" as const,
      laneLabel: "Sections",
      label: "Chorus",
      start_s: 12,
      end_s: 30,
      confidence: 0.812,
      reference: "S3",
      detail: null,
      section_id: "S3",
      created_by: null,
      caption: "",
      summary: null,
      raw: {
        section_id: "S3",
        start: 12,
        end: 30,
        label: "003 Chorus (0.81)",
        description: null,
        confidence: 0.812,
        function: "chorus",
        function_confidence: 0.91,
        function_status: "ok",
        same_label_as: "S1",
      },
    };
    const fields = blockFields("sections", sel);
    expect(val(fields, "function")).toBe("chorus");
    expect(val(fields, "function_confidence")).toBe("0.91");
    expect(val(fields, "function_status")).toBe("ok");
    expect(val(fields, "same_label_as")).toBe("S1");
    expect(fields.some((f) => f.label === "section_character")).toBe(false);
    expect(fields.some((f) => f.label === "repetition_group")).toBe(false);
    expect(fields.some((f) => f.label === "Form role")).toBe(false);
    expect(fields.some((f) => f.label === "Repetition group")).toBe(false);
  });

  it("still shows same_label_as on a section's first occurrence, where it is null", () => {
    const sel = {
      laneLabel: "Sections",
      label: "Intro",
      start_s: 0,
      end_s: 30,
      confidence: 0.9,
      reference: "S1",
      detail: null,
      section_id: "S1",
      created_by: null,
      caption: "",
      summary: null,
      raw: {
        section_id: "S1",
        start: 0,
        end: 30,
        label: "001 Intro (0.44)",
        description: null,
        confidence: 0.9,
        function: "intro",
        function_confidence: 0.44,
        function_status: "known",
        same_label_as: null,
      },
    };
    const fields = blockFields("sections", sel);
    expect(fields.some((f) => f.label === "same_label_as")).toBe(true);
    expect(val(fields, "same_label_as")).toBe("null");
  });
});

describe("selectionFromMarker + blockFields — lane markers", () => {
  it("drum marker", () => {
    const marker: LaneMarker = {
      laneId: "drums",
      id: "d-12",
      time: 4.2,
      kind: "drum",
      raw: { id: "d-12", time: 4.2, end_s: 4.2, event_type: "kick" },
    };
    const sel = selectionFromMarker(marker);
    expect(sel.laneLabel).toBe("Drum Density");
    expect(sel.start_s).toBeCloseTo(4.2);
    const fields = blockFields("drums", sel);
    expect(val(fields, "Event type")).toBe("kick");
  });

  it("energy accent candidate", () => {
    const marker: LaneMarker = {
      laneId: "energy",
      id: "a-3",
      time: 61,
      kind: "accent",
      intensity: 0.9,
      raw: { id: "a-3", time: 61, intensity: 0.9, kind: "impact" },
    };
    const sel = selectionFromMarker(marker);
    const fields = blockFields("energy", sel);
    expect(val(fields, "Intensity")).toBe("0.90");
    expect(val(fields, "Kind")).toBe("impact");
  });

  it("machine event with nested evidence summary + section_id", () => {
    const marker: LaneMarker = {
      laneId: "machineEvents",
      id: "m-1",
      time: 20,
      kind: "machine",
      raw: {
        id: "m-1",
        label: "riser",
        start_s: 20,
        end_s: 24,
        confidence: 0.66,
        section_id: "S2",
        created_by: "rule:riser",
        evidence: { summary: "spectral flux ramp" },
      },
    };
    const sel = selectionFromMarker(marker);
    expect(sel.summary).toBe("spectral flux ramp");
    const fields = blockFields("machineEvents", sel);
    expect(val(fields, "Window")).toBe("0:20.0–0:24.0");
    expect(val(fields, "Confidence")).toBe("0.66");
    expect(val(fields, "Section")).toBe("S2");
    expect(val(fields, "Created by")).toBe("rule:riser");
  });
});

