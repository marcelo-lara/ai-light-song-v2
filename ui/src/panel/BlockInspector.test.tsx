// BlockInspector — plan v1.5 item 9: the "Create human hint" action, and the
// "Create human section" action on the section-shaped lanes.

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { BlockSelection } from "./blockFields";
import { BlockInspector } from "./BlockInspector";

const selection: BlockSelection = {
  laneId: "sections",
  laneLabel: "Sections",
  label: "intro",
  start_s: 0.01,
  end_s: 30.0,
  confidence: null,
  reference: "section-001",
  detail: null,
  section_id: null,
  created_by: null,
  caption: "0:00.0–0:30.0",
  summary: "Functional section `intro`.",
  raw: { name: "intro", start_s: 0.01, end_s: 30.0 },
};

describe("BlockInspector — Create human hint", () => {
  it("renders the button with an accessible name containing 'Create human hint'", () => {
    const { getByTestId } = render(
      <BlockInspector selection={selection} onCreateHint={() => {}} onCreateSection={() => {}} />,
    );
    const btn = getByTestId("promote-hint");
    expect(btn).toBeTruthy();
    expect(btn.textContent).toContain("Create human hint");
  });

  it("calls onCreateHint with the exact selection object it was given", () => {
    const onCreateHint = vi.fn();
    const { getByTestId } = render(
      <BlockInspector selection={selection} onCreateHint={onCreateHint} onCreateSection={() => {}} />,
    );
    fireEvent.click(getByTestId("promote-hint"));
    expect(onCreateHint).toHaveBeenCalledTimes(1);
    expect(onCreateHint).toHaveBeenCalledWith(selection);
  });
});

describe("BlockInspector — Create human section", () => {
  it.each(["allin1Sections", "segmentSeeds", "moisesSections"])(
    "%s blocks get 'Create human section' routed to onCreateSection",
    (laneId) => {
      const onCreateHint = vi.fn();
      const onCreateSection = vi.fn();
      const sel = { ...selection, laneId };
      const { getByTestId, queryByTestId } = render(
        <BlockInspector selection={sel} onCreateHint={onCreateHint} onCreateSection={onCreateSection} />,
      );
      expect(queryByTestId("promote-hint")).toBeNull();
      const btn = getByTestId("promote-section");
      expect(btn.textContent).toContain("Create human section");
      fireEvent.click(btn);
      expect(onCreateSection).toHaveBeenCalledWith(sel);
      expect(onCreateHint).not.toHaveBeenCalled();
    },
  );
});
