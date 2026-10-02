// PendingProposalsPanel — playhead in-window highlight and click-to-seek
// (R3-override) coverage. `../data/loaders` is mocked so the panel's initial
// `loadPendingProposals` resolves
// synchronously with fixture data instead of hitting `/data`.

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PendingProposalsFile } from "../data/types";

import { PendingProposalsPanel } from "./PendingProposalsPanel";

vi.mock("../data/loaders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../data/loaders")>();
  return {
    ...actual,
    loadPendingProposals: vi.fn(),
  };
});

import { loadPendingProposals } from "../data/loaders";

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
  ],
};

function mockLoaders() {
  vi.mocked(loadPendingProposals).mockResolvedValue({ ok: true, data: QUEUE });
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

  it("is not in-window when currentTime falls outside every card's span", async () => {
    mockLoaders();
    const { findByText } = render(
      <PendingProposalsPanel {...base} currentTime={0} />,
    );
    await findByText("Drop payoff");
    expect(
      document.querySelector('[data-proposal-id="hint-a"]')?.getAttribute("data-in-window"),
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
});
