// LaneEventsPanel — plan v1.5 item 3: the stacked lane-events list.

import { fireEvent, render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { BlockEnergyFile } from "../data/types";

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
  onSelectMarker: () => {},
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

  it("shows the right-side id as the numeric suffix after the last dash", () => {
    const { container } = render(
      <LaneEventsPanel {...base} blocks={BLOCKS} />,
    );
    expect(
      Array.from(
        container.querySelectorAll(".lane-events__blockid"),
        (n) => n.textContent,
      ),
    ).toEqual(["001", "002", "003"]);
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

  it("double-clicking a card calls onSelectMarker with a marker for that block", () => {
    const onSelectMarker = vi.fn();
    const { container } = render(
      <LaneEventsPanel {...base} blocks={BLOCKS} onSelectMarker={onSelectMarker} />,
    );
    fireEvent.dblClick(
      container.querySelector(
        '[data-testid="lane-event-hint-002"]',
      ) as HTMLElement,
    );
    expect(onSelectMarker).toHaveBeenCalledWith(
      expect.objectContaining({ laneId: base.laneId, id: "hint-002" }),
    );
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

  // playhead-window left-border marker: independent of `data-active`, and
  // multiple overlapping cards can all carry it at once.
  it("marks every card whose window covers currentTime, not just the active one", () => {
    const OVERLAPPING = [
      block({ id: "outer", start_s: 0, end_s: 100 }),
      block({ id: "inner", start_s: 40, end_s: 60 }),
    ];
    const { container } = render(
      <LaneEventsPanel {...base} blocks={OVERLAPPING} currentTime={50} />,
    );
    expect(
      Array.from(
        container.querySelectorAll(".lane-events__card"),
        (c) => (c as HTMLElement).dataset.inWindow,
      ),
    ).toEqual(["true", "true"]);
    // only the innermost is `data-active`.
    expect(
      container.querySelectorAll('.lane-events__card[data-active="true"]'),
    ).toHaveLength(1);
  });

  it("marks no card in-window for a time in a gap", () => {
    const { container } = render(
      <LaneEventsPanel {...base} blocks={TIMED} currentTime={50} />,
    );
    expect(
      Array.from(
        container.querySelectorAll(".lane-events__card"),
        (c) => (c as HTMLElement).dataset.inWindow,
      ),
    ).toEqual(["false", "false", "false"]);
  });

  // v3.4 item 4 (D4.1): the energy/tension rating controls, shown only when a
  // `blockEnergy` prop is supplied (the Human Hints panel).
  describe("block energy/tension ratings", () => {
    const file: BlockEnergyFile = {
      schema_version: "1.0",
      song_name: "s",
      ratings: [{ hint_id: "hint-001", energy: 5, tension: 4 }],
    };
    const withRatings = (over: Partial<Parameters<typeof LaneEventsPanel>[0]> = {}) => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const utils = render(
        <LaneEventsPanel
          {...base}
          blocks={BLOCKS}
          blockEnergy={{ file, onSave }}
          {...over}
        />,
      );
      return { ...utils, onSave };
    };

    it("renders an energy and a tension selector (5 segments each) per card", () => {
      const { container } = withRatings();
      const groups = container.querySelectorAll(".lane-events__rating");
      expect(groups).toHaveLength(3);
      for (const g of groups) {
        expect(g.querySelectorAll('[data-axis="energy"] .seg-rating__btn')).toHaveLength(5);
        expect(g.querySelectorAll('[data-axis="tension"] .seg-rating__btn')).toHaveLength(5);
      }
    });

    it("pre-fills the pressed segment from the loaded file", () => {
      const { getByTestId } = withRatings();
      expect(getByTestId("block-energy-hint-001-energy-5").getAttribute("aria-pressed")).toBe("true");
      expect(getByTestId("block-energy-hint-001-tension-4").getAttribute("aria-pressed")).toBe("true");
      // the other energy segments are not pressed
      expect(getByTestId("block-energy-hint-001-energy-3").getAttribute("aria-pressed")).toBe("false");
    });

    it("shows an explicit unrated state (no segment pressed) for an unrated block", () => {
      const { container } = withRatings();
      const card = container.querySelector('[data-testid="block-energy-hint-002"]')!;
      expect(card.querySelectorAll('.seg-rating__btn[aria-pressed="true"]')).toHaveLength(0);
      expect(
        Array.from(
          card.querySelectorAll(".seg-rating"),
          (s) => (s as HTMLElement).dataset.value,
        ),
      ).toEqual(["unrated", "unrated"]);
    });

    it("shows N / M blocks rated in the header", () => {
      const { getByTestId } = withRatings();
      expect(getByTestId("block-energy-count").textContent).toBe("1 / 3 blocks rated");
    });

    it("Save calls the client with a draft per block", async () => {
      const { getByTestId, onSave } = withRatings();
      fireEvent.click(getByTestId("block-energy-hint-002-energy-3"));
      expect(getByTestId("block-energy-hint-002-energy-3").getAttribute("aria-pressed")).toBe("true");
      fireEvent.click(getByTestId("block-energy-save"));
      await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
      const drafts = onSave.mock.calls[0]![0] as Array<{
        hint_id: string;
        energy: number | null;
        tension: number | null;
      }>;
      expect(drafts).toEqual([
        { hint_id: "hint-001", energy: 5, tension: 4 },
        { hint_id: "hint-002", energy: 3, tension: null },
        { hint_id: "hint-003", energy: null, tension: null },
      ]);
    });

    it("clicking a pressed segment again clears it back to unrated", () => {
      const { getByTestId } = withRatings();
      fireEvent.click(getByTestId("block-energy-hint-001-energy-5"));
      expect(getByTestId("block-energy-hint-001-energy-5").getAttribute("aria-pressed")).toBe("false");
    });

    it("closing the panel does not write", () => {
      const { getByLabelText, onSave } = withRatings();
      fireEvent.click(getByLabelText("Close panel"));
      expect(onSave).not.toHaveBeenCalled();
    });

    it("renders no rating controls without the blockEnergy prop", () => {
      const { container } = render(
        <LaneEventsPanel {...base} blocks={BLOCKS} />,
      );
      expect(container.querySelector(".lane-events__rating")).toBeNull();
      expect(container.querySelector('[data-testid="block-energy-save"]')).toBeNull();
    });
  });

  // v3.4 item 5 — the ✔ token-validation button, shown only for the Moises
  // Lyrics panel's word-token cards.
  describe("Moises lyric-token validation", () => {
    const LYRIC_BLOCKS: SparseBlock[] = [
      block({ id: "1", label: "<SOL>", laneLabel: "Moises Lyrics" }),
      block({
        id: "2",
        label: "We",
        laneLabel: "Moises Lyrics",
        lyricValidatable: true,
        lyricTokenId: 2,
      }),
      block({
        id: "3",
        label: "are",
        laneLabel: "Moises Lyrics",
        tintId: "moisesLyricsValidated",
        lyricValidatable: true,
        lyricTokenId: 3,
      }),
    ];
    const lyricBase = { ...base, laneId: "moisesLyrics", laneLabel: "Moises Lyrics" };

    const withLyric = (validatedIds = new Set<number>([3])) => {
      const onToggle = vi.fn();
      const onSelectBlock = vi.fn();
      const utils = render(
        <LaneEventsPanel
          {...lyricBase}
          blocks={LYRIC_BLOCKS}
          onSelectBlock={onSelectBlock}
          lyricValidation={{ validatedIds, onToggle }}
        />,
      );
      return { ...utils, onToggle, onSelectBlock };
    };

    it("gives every word token exactly one ✔ button and the marker none", () => {
      const { container } = withLyric();
      expect(container.querySelectorAll(".lane-events__validate")).toHaveLength(2);
      const solCard = container.querySelector('[data-block-id="1"]')!;
      expect(solCard.querySelector(".lane-events__validate")).toBeNull();
    });

    it("reflects the validated state via aria-pressed", () => {
      const { getByTestId } = withLyric();
      expect(getByTestId("lyric-validate-2").getAttribute("aria-pressed")).toBe("false");
      expect(getByTestId("lyric-validate-3").getAttribute("aria-pressed")).toBe("true");
    });

    it("clicking ✔ toggles via onToggle and never seeks", () => {
      const { getByTestId, onToggle, onSelectBlock } = withLyric();
      fireEvent.click(getByTestId("lyric-validate-2"));
      expect(onToggle).toHaveBeenCalledWith(2, true);
      fireEvent.click(getByTestId("lyric-validate-3"));
      expect(onToggle).toHaveBeenCalledWith(3, false);
      expect(onSelectBlock).not.toHaveBeenCalled();
    });

    it("renders no ✔ button without the lyricValidation prop", () => {
      const { container } = render(
        <LaneEventsPanel {...lyricBase} blocks={LYRIC_BLOCKS} />,
      );
      expect(container.querySelector(".lane-events__validate")).toBeNull();
    });
  });
});
