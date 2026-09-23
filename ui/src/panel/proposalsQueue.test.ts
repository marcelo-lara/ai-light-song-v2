import { describe, expect, it } from "vitest";

import type {
  HumanHint,
  HumanSegmentsFile,
  PendingProposal,
  PendingProposalsFile,
  SectionsTopLevel,
} from "../data/types";

import {
  applySectionFieldToSegments,
  bestOverlapIndex,
  hintDraftFromProposal,
  partitionProposals,
  sectionSpan,
} from "./proposalsQueue";

const hintProposal = (over: Partial<PendingProposal> = {}): PendingProposal => ({
  id: "prop-1",
  type: "hint",
  status: "pending",
  created_at: "2026-09-22T00:00:00Z",
  rejection_reason: null,
  evidence: "loudness spike",
  hint: { start: 10, end: 12, title: "Drop payoff", summary: "loudness spike" },
  ...over,
} as PendingProposal);

const sectionFieldProposal = (
  over: Partial<PendingProposal> = {},
): PendingProposal =>
  ({
    id: "prop-2",
    type: "section_field",
    status: "pending",
    created_at: "2026-09-22T00:00:01Z",
    rejection_reason: null,
    evidence: "gesture build overlaps",
    section_field: { section_id: "section-001", field: "tension", value: 4 },
    ...over,
  }) as PendingProposal;

describe("partitionProposals", () => {
  it("splits pending from decided, newest-decided first", () => {
    const file: PendingProposalsFile = {
      schema_version: "1.0",
      song_name: "ayuni",
      proposals: [
        hintProposal({ id: "a", status: "approved", created_at: "2026-09-20T00:00:00Z" }),
        sectionFieldProposal({ id: "b", status: "pending" }),
        hintProposal({ id: "c", status: "rejected", created_at: "2026-09-21T00:00:00Z" }),
      ],
    };
    const { pending, decided } = partitionProposals(file);
    expect(pending.map((p) => p.id)).toEqual(["b"]);
    expect(decided.map((p) => p.id)).toEqual(["c", "a"]);
  });
});

describe("sectionSpan", () => {
  const sections: SectionsTopLevel = [
    {
      section_id: "section-001",
      start: 0,
      end: 10,
      label: "001 Intro",
      description: null,
      function: "intro",
      function_confidence: 0.8,
      function_status: "known",
      same_label_as: null,
      confidence: 0.8,
      key: "C major",
    },
  ];

  it("returns the span for a known section_id", () => {
    expect(sectionSpan(sections, "section-001")).toEqual({ start: 0, end: 10 });
  });

  it("returns null for an unknown section_id", () => {
    expect(sectionSpan(sections, "section-999")).toBeNull();
  });
});

describe("bestOverlapIndex", () => {
  const segments: HumanSegmentsFile = [
    { start: 0, end: 5 },
    { start: 5, end: 20 },
    { start: 20, end: 30 },
  ];

  it("picks the row with the largest positive overlap", () => {
    expect(bestOverlapIndex(segments, 4, 22)).toBe(1);
  });

  it("returns -1 when nothing overlaps", () => {
    expect(bestOverlapIndex(segments, 100, 110)).toBe(-1);
  });
});

describe("applySectionFieldToSegments", () => {
  it("sets a scalar field on the best-overlapping existing row, immutably", () => {
    const segments: HumanSegmentsFile = [{ start: 0, end: 10, energy: 2 }];
    const next = applySectionFieldToSegments(segments, { start: 0, end: 10 }, "tension", 4);
    expect(next).not.toBe(segments);
    expect(next[0]).toEqual({ start: 0, end: 10, energy: 2, tension: 4 });
    expect(segments[0]).toEqual({ start: 0, end: 10, energy: 2 });
  });

  it("merges a rhythm.<stem> field onto any existing rhythm object", () => {
    const segments: HumanSegmentsFile = [
      { start: 0, end: 10, rhythm: { bass: "quarter" } },
    ];
    const next = applySectionFieldToSegments(
      segments,
      { start: 0, end: 10 },
      "rhythm.drums",
      "eighth",
    );
    expect(next[0]!.rhythm).toEqual({ bass: "quarter", drums: "eighth" });
  });

  it("creates a new row at the section's own span when nothing overlaps", () => {
    const segments: HumanSegmentsFile = [{ start: 0, end: 5 }];
    const next = applySectionFieldToSegments(segments, { start: 50, end: 60 }, "energy", 3);
    expect(next).toHaveLength(2);
    expect(next[1]).toEqual({ start: 50, end: 60, energy: 3 });
  });

  it("rejects an out-of-range scalar value", () => {
    const segments: HumanSegmentsFile = [{ start: 0, end: 10 }];
    expect(() =>
      applySectionFieldToSegments(segments, { start: 0, end: 10 }, "energy", 9),
    ).toThrow();
  });
});

describe("hintDraftFromProposal", () => {
  it("builds a HintDraft carrying the proposal id as an informative note", () => {
    const existing: HumanHint[] = [
      {
        id: "human-hint-1",
        title: "existing",
        start_time: 1,
        end_time: 2,
        summary: "",
        lighting_hint: "",
      },
    ];
    const proposal = hintProposal() as Extract<PendingProposal, { type: "hint" }>;
    const draft = hintDraftFromProposal(proposal, existing);
    expect(draft).toEqual({
      id: "human-hint-2",
      title: "Drop payoff",
      start_time: 10,
      end_time: 12,
      summary: "loudness spike",
      lighting_hint: "",
      captured_from: "MCP proposal prop-1",
      type: "review",
    });
  });
});
