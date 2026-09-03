// LaneEventsPanel — plan v1.5 item 3: the stacked lane-events list.

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SparseBlock } from "../timeline/laneContent";

import { LaneEventsPanel } from "./LaneEventsPanel";

function block(over: Partial<SparseBlock> & { id: string }): SparseBlock {
  return {
    start_s: 0,
    end_s: 1,
    label: over.id,
    laneLabel: "Human Hints",
    caption: `caption ${over.id}`,
    reference: over.id,
    detail: "-",
    summary: "-",
    raw: {},
    ...over,
  };
}

const BLOCKS = [
  block({ id: "hint-001", label: "Drop - approach", caption: "0:40.0–0:48.0" }),
  block({ id: "hint-002", label: "drop build", caption: "0:52.0–1:00.0" }),
  block({ id: "hint-003", label: "drop tension", caption: "1:04.0–1:12.0" }),
];

const base = {
  laneId: "humanHints",
  laneLabel: "Human Hints",
  status: "ready" as const,
  error: null,
  currentTime: 0,
  playing: false,
  onClose: () => {},
  onSelectBlock: () => {},
};

describe("LaneEventsPanel", () => {
  it("renders one card per block, in source order", () => {
    const { container } = render(
      <LaneEventsPanel {...base} blocks={BLOCKS} />,
    );
    const cards = container.querySelectorAll<HTMLElement>(".lane-events__card");
    expect(Array.from(cards, (c) => c.dataset.blockId)).toEqual([
      "hint-001",
      "hint-002",
      "hint-003",
    ]);
    expect(
      container.querySelector('[data-testid="lane-events-panel"]')?.getAttribute(
        "data-lane",
      ),
    ).toBe("humanHints");
    expect(container.querySelector(".lane-events__count")?.textContent).toBe(
      "3 events",
    );
  });

  it("card labels and captions match the blocks", () => {
    const { container } = render(
      <LaneEventsPanel {...base} blocks={BLOCKS} />,
    );
    expect(
      Array.from(
        container.querySelectorAll(".lane-events__label"),
        (n) => n.textContent,
      ),
    ).toEqual(["Drop - approach", "drop build", "drop tension"]);
    expect(
      Array.from(
        container.querySelectorAll(".lane-events__caption"),
        (n) => n.textContent,
      ),
    ).toEqual(["0:40.0–0:48.0", "0:52.0–1:00.0", "1:04.0–1:12.0"]);
  });

  it("clicking a card calls onSelectBlock with that block", () => {
    const onSelectBlock = vi.fn();
    const { container } = render(
      <LaneEventsPanel {...base} blocks={BLOCKS} onSelectBlock={onSelectBlock} />,
    );
    fireEvent.click(
      container.querySelector(
        '[data-testid="lane-event-hint-002"]',
      ) as HTMLElement,
    );
    expect(onSelectBlock).toHaveBeenCalledWith(BLOCKS[1]);
  });

  it("renders the loading state string", () => {
    const { container } = render(
      <LaneEventsPanel {...base} status="loading" blocks={[]} />,
    );
    expect(container.textContent).toContain("Loading…");
    expect(
      container.querySelector('[data-testid="lane-events-panel"]'),
    ).toBeNull();
  });

  it("renders the error state string", () => {
    const { container } = render(
      <LaneEventsPanel
        {...base}
        status="error"
        error="boom"
        blocks={[]}
      />,
    );
    expect(container.textContent).toContain("Unavailable — boom");
  });

  it("renders the ready-empty state string", () => {
    const { container } = render(
      <LaneEventsPanel {...base} status="ready" blocks={[]} />,
    );
    expect(container.textContent).toContain("No data in this artifact");
  });

  // item 4 / R1: the active-card highlight.
  const TIMED = [
    block({ id: "hint-001", start_s: 40, end_s: 48 }),
    block({ id: "hint-002", start_s: 52, end_s: 60 }),
    block({ id: "hint-003", start_s: 64, end_s: 72 }),
  ];

  it("marks exactly one card active for a time inside a block", () => {
    const { container } = render(
      <LaneEventsPanel {...base} blocks={TIMED} currentTime={54} />,
    );
    const active = container.querySelectorAll<HTMLElement>(
      '.lane-events__card[data-active="true"]',
    );
    expect(active).toHaveLength(1);
    expect(active[0]?.dataset.blockId).toBe("hint-002");
    expect(active[0]?.getAttribute("aria-current")).toBe("true");
  });

  it("marks no card active for a time in a gap", () => {
    const { container } = render(
      <LaneEventsPanel {...base} blocks={TIMED} currentTime={50} />,
    );
    expect(
      container.querySelectorAll('.lane-events__card[data-active="true"]'),
    ).toHaveLength(0);
    expect(
      Array.from(
        container.querySelectorAll(".lane-events__card"),
        (c) => (c as HTMLElement).dataset.active,
      ),
    ).toEqual(["false", "false", "false"]);
  });
});
