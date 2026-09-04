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
    start: 12,
    end: 30,
    label: "003 Momentum Lift (0.80)",
    description: "energy rises into the chorus",
    hints: [],
    section_id: "S3",
    form_role: "chorus",
    energy_character: "high",
    repetition_group: "A",
    confidence: 0.8,
  };
  const block = { section } as { section: SectionRow };

  it("normalises name, window, confidence, reference", () => {
    const sel = selectionFromSection(block, "segments");
    expect(sel.label).toBe("chorus");
    expect(sel.start_s).toBe(12);
    expect(sel.end_s).toBe(30);
    expect(sel.confidence).toBe(0.8);
    expect(sel.reference).toBe("S3");
    expect(sel.summary).toBe("energy rises into the chorus");
  });

  it("cleans a projection label when there is no form_role", () => {
    const sel = selectionFromSection(
      { section: { ...section, form_role: null } } as { section: SectionRow },
      "segments",
    );
    expect(sel.label).toBe("Momentum Lift");
  });
});

describe("blockFields — segments / sections", () => {
  const sel = selectionFromSection(
    {
      section: {
        start: 12,
        end: 30,
        label: "Chorus",
        description: null,
        hints: [],
        section_id: "S3",
        form_role: "chorus",
        energy_character: "high",
        repetition_group: "A",
        confidence: 0.812,
      },
    } as { section: SectionRow },
    "segments",
  );

  it("emits the shared rows in buildSelectionFields order + lane extras", () => {
    const fields = blockFields("segments", sel);
    expect(fields[0]).toEqual({ label: "Lane", value: "Segments" });
    expect(val(fields, "Window")).toBe("0:12.0–0:30.0");
    expect(val(fields, "Confidence")).toBe("0.81");
    expect(val(fields, "Reference")).toBe("S3");
    expect(val(fields, "Section")).toBe("S3");
    expect(val(fields, "Form role")).toBe("chorus");
    expect(val(fields, "Repetition group")).toBe("A");
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

