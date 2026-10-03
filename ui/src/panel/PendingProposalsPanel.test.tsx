// PendingProposalsPanel — playhead in-window highlight and click-to-seek
// (R3-override) coverage. `../data/loaders` is mocked so the panel's initial
// `loadPendingProposals` resolves
// synchronously with fixture data instead of hitting `/data`.

import { fireEvent, render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PendingProposalsFile } from "../data/types";

import { saveProposalDecision } from "../data/saveProposalDecision";
import { PendingProposalsPanel } from "./PendingProposalsPanel";

vi.mock("../data/loaders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../data/loaders")>();
  return {
    ...actual,
    loadPendingProposals: vi.fn(),
  };
});

import { loadPendingProposals } from "../data/loaders";

vi.mock("../data/saveProposalDecision", () => ({ saveProposalDecision: vi.fn() }));

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

const VERDICT_QUEUE: PendingProposalsFile = {
  schema_version: "1.0",
  song_name: "ayuni",
  proposals: [
    QUEUE.proposals[0]!,
    {
      id: "vc-1",
      type: "verdict_check",
      status: "pending",
      created_at: "2026-10-01T00:00:00Z",
      rejection_reason: null,
      evidence: "audio shows one drop",
      verdict_check: {
        field: "drops",
        claim: "The hint says two drops",
        evidence: {
          stems: { read: "bass entries", showed: "bass enters once" },
          drum_density: { read: "drum_density", showed: "dense from section-003" },
          dropouts: { read: "dropouts", showed: "one dropout" },
          loudness: { read: "loudness", showed: "p90 once" },
          web_search: { read: "web", showed: "a wiki says two" },
        },
        cannot_settle: "audio shows one, the web says two",
        question: "Are there two drops?",
      },
    },
  ],
};

describe("PendingProposalsPanel — verdict_check card", () => {
  it("renders the claim, five evidence rows, the question and Confirm / Reject beside a hint card", async () => {
    vi.mocked(loadPendingProposals).mockResolvedValue({ ok: true, data: VERDICT_QUEUE });
    const { findByText } = render(<PendingProposalsPanel {...base} currentTime={0} />);
    await findByText("The hint says two drops");
    expect(document.querySelectorAll('[data-testid="pending-proposal-card"]')).toHaveLength(2);
    expect(document.querySelectorAll("[data-evidence-kind]")).toHaveLength(5);
    expect(document.querySelector('[data-testid="verdict-check-question"]')?.textContent).toBe(
      "Are there two drops?",
    );
    const card = document.querySelector('[data-proposal-type="verdict_check"]') as HTMLElement;
    const buttons = Array.from(card.querySelectorAll("button")).map((b) => b.textContent);
    expect(buttons).toEqual(["Reject", "Confirm"]);
  });

  it("Reject needs a reason before it can be sent", async () => {
    vi.mocked(loadPendingProposals).mockResolvedValue({ ok: true, data: VERDICT_QUEUE });
    vi.mocked(saveProposalDecision).mockClear();
    const { findByText } = render(<PendingProposalsPanel {...base} currentTime={0} />);
    await findByText("The hint says two drops");
    const card = document.querySelector('[data-proposal-type="verdict_check"]') as HTMLElement;
    fireEvent.click(Array.from(card.querySelectorAll("button")).find((b) => b.textContent === "Reject")!);
    const send = Array.from(card.querySelectorAll("button")).find(
      (b) => b.textContent === "Confirm reject",
    ) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(card.querySelector("textarea")!, { target: { value: "  the audio disagrees " } });
    expect(send.disabled).toBe(false);
    vi.mocked(saveProposalDecision).mockResolvedValue(VERDICT_QUEUE);
    fireEvent.click(send);
    await waitFor(() =>
      expect(saveProposalDecision).toHaveBeenCalledWith("ayuni", {
        id: "vc-1",
        status: "rejected",
        rejection_reason: "the audio disagrees",
      }),
    );
  });

  it("Confirm approves with no times and no re-run reminder", async () => {
    vi.mocked(loadPendingProposals).mockResolvedValue({ ok: true, data: VERDICT_QUEUE });
    vi.mocked(saveProposalDecision).mockReset().mockResolvedValue(VERDICT_QUEUE);
    const { findByText } = render(<PendingProposalsPanel {...base} currentTime={0} />);
    await findByText("The hint says two drops");
    const card = document.querySelector('[data-proposal-type="verdict_check"]') as HTMLElement;
    fireEvent.click(Array.from(card.querySelectorAll("button")).find((b) => b.textContent === "Confirm")!);
    await waitFor(() =>
      expect(saveProposalDecision).toHaveBeenCalledWith("ayuni", { id: "vc-1", status: "approved" }),
    );
    expect(document.querySelector('[data-testid="rerun-reminder"]')).toBeNull();
  });
});
