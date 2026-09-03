// BlockInspector — plan v1.5 item 9: the "Create human hint" action.

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { BlockSelection } from "./blockFields";
import { BlockInspector } from "./BlockInspector";

const selection: BlockSelection = {
  laneId: "allin1Sections",
  laneLabel: "allin1 Sections",
  label: "intro",
  start_s: 0.01,
  end_s: 30.0,
  confidence: null,
  reference: "allin1-001",
  detail: null,
  section_id: null,
  created_by: null,
  caption: "0:00.0–0:30.0",
  summary: "allin1 functional section `intro`.",
  raw: { name: "intro", start_s: 0.01, end_s: 30.0 },
};

describe("BlockInspector — Create human hint", () => {
  it("renders the button with an accessible name containing 'Create human hint'", () => {
    const { getByTestId } = render(
      <BlockInspector selection={selection} onCreateHint={() => {}} />,
    );
    const btn = getByTestId("promote-hint");
    expect(btn).toBeTruthy();
    expect(btn.textContent).toContain("Create human hint");
  });

  it("calls onCreateHint with the exact selection object it was given", () => {
    const onCreateHint = vi.fn();
    const { getByTestId } = render(
      <BlockInspector selection={selection} onCreateHint={onCreateHint} />,
    );
    fireEvent.click(getByTestId("promote-hint"));
    expect(onCreateHint).toHaveBeenCalledTimes(1);
    expect(onCreateHint).toHaveBeenCalledWith(selection);
  });
});
