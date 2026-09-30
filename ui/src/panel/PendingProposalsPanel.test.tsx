// PendingProposalsPanel — playhead in-window highlight and click-to-seek
// (R3-override) coverage. `../data/loaders` is mocked so the panel's initial
// `Promise.all([loadPendingProposals, loadSectionsTopLevel])` resolves
// synchronously with fixture data instead of hitting `/data`.

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PendingProposalsFile, SectionsTopLevel } from "../data/types";

import { PendingProposalsPanel } from "./PendingProposalsPanel";

vi.mock("../data/loaders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../data/loaders")>();
  return {
    ...actual,
    loadPendingProposals: vi.fn(),
    loadSectionsTopLevel: vi.fn(),
  };
});

import { loadPendingProposals, loadSectionsTopLevel } from "../data/loaders";

const SECTIONS: SectionsTopLevel = [
  {
    section_id: "section-001",
    start: 20,
    end: 30,
    label: "001 Chorus",
    description: null,
    function: "chorus",
    function_confidence: 0.8,
    function_status: "known",
    same_label_as: null,
    confidence: 0.8,
    key: "C major",
  },
];

const QUEUE: PendingProposalsFile = {
  schema_version: "1.0",
  song_name: "ayuni",
  proposals: [
    {
      id: "hint-a",
      type: "hint",
      status: "pending",
      created_at: "2026-09-22T00:00:00Z",
      rejection_reason: null,
      evidence: "loudness spike",
      hint: { start: 10, end: 12, title: "Drop payoff", summary: "" },
    } as PendingProposalsFile["proposals"][number],
    {
      id: "section-a",
      type: "section_field",
      status: "pending",
      created_at: "2026-09-22T00:00:01Z",
      rejection_reason: null,
      evidence: "gesture build overlaps",
      section_field: { section_id: "section-001", field: "tension", value: 4 },
    } as PendingProposalsFile["proposals"][number],
  ],
};

function mockLoaders() {
  vi.mocked(loadPendingProposals).mockResolvedValue({ ok: true, data: QUEUE });
  vi.mocked(loadSectionsTopLevel).mockResolvedValue({ ok: true, data: SECTIONS });
}

const base = {
  song: "ayuni",
  onClose: () => {},
};

describe("PendingProposalsPanel — in-window highlight", () => {
  it("marks a hint card in-window when currentTime falls in its proposed span", async () => {
    mockLoaders();
    const { findByText } = render(
      <PendingProposalsPanel {...base} currentTime={11} />,
    );
    await findByText("Drop payoff");
    const card = document.querySelector('[data-proposal-id="hint-a"]');
    expect(card?.getAttribute("data-in-window")).toBe("true");
  });

  it("uses the operator's dragged correction, not the proposed span, once edited", async () => {
    mockLoaders();
    const { findByText } = render(
      <PendingProposalsPanel
        {...base}
        currentTime={16}
        timeEdits={{ "hint-a": { start: 14, end: 18 } }}
      />,
    );
    await findByText("Drop payoff");
    const card = document.querySelector('[data-proposal-id="hint-a"]');
    expect(card?.getAttribute("data-in-window")).toBe("true");
  });

  it("marks a section_field card in-window against its published section span", async () => {
    mockLoaders();
    const { findByText } = render(
      <PendingProposalsPanel {...base} currentTime={25} />,
    );
    await findByText("Section field");
    const card = document.querySelector('[data-proposal-id="section-a"]');
    expect(card?.getAttribute("data-in-window")).toBe("true");
  });

  it("is not in-window when currentTime falls outside every card's span", async () => {
    mockLoaders();
    const { findByText } = render(
      <PendingProposalsPanel {...base} currentTime={0} />,
    );
    await findByText("Drop payoff");
    expect(
      document.querySelector('[data-proposal-id="hint-a"]')?.getAttribute("data-in-window"),
    ).toBe("false");
    expect(
      document.querySelector('[data-proposal-id="section-a"]')?.getAttribute("data-in-window"),
    ).toBe("false");
  });
});

describe("PendingProposalsPanel — click seeks to window start", () => {
  it("seeks a hint card to its proposed start", async () => {
    mockLoaders();
    const onSeek = vi.fn();
    const { findByText } = render(
      <PendingProposalsPanel {...base} currentTime={0} onSeek={onSeek} />,
    );
    const label = await findByText("Drop payoff");
    fireEvent.click(label);
    expect(onSeek).toHaveBeenCalledWith(10);
  });

  it("seeks an edited hint card to the operator's corrected start", async () => {
    mockLoaders();
    const onSeek = vi.fn();
    const { findByText } = render(
      <PendingProposalsPanel
        {...base}
        currentTime={0}
        onSeek={onSeek}
        timeEdits={{ "hint-a": { start: 14, end: 18 } }}
      />,
    );
    const label = await findByText("Drop payoff");
    fireEvent.click(label);
    expect(onSeek).toHaveBeenCalledWith(14);
  });

  it("seeks a section_field card to its section's published start", async () => {
    mockLoaders();
    const onSeek = vi.fn();
    const { findByText } = render(
      <PendingProposalsPanel {...base} currentTime={0} onSeek={onSeek} />,
    );
    const label = await findByText("Section field");
    fireEvent.click(label);
    expect(onSeek).toHaveBeenCalledWith(20);
  });
});
