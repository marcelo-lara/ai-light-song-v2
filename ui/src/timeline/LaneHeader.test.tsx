// LaneHeader — items 5 (collapsed = title only) and 6 (caret keeps a fixed slot).

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LaneHeader } from "./TimelineGrid";
import {
  COLLAPSED_STRIP_HEIGHT,
  collapsedLaneHeight,
  type Lane,
} from "./laneState";

function makeLane(expanded: boolean): Lane {
  return {
    id: "rmsLoudness",
    label: "RMS Loudness",
    sub: "essentia · mix + 4 stems",
    kind: "rms",
    height: 112,
    expanded,
    visible: true,
    renderHeight: expanded ? 112 : collapsedLaneHeight(),
  };
}

const renderHead = (expanded: boolean) => {
  const { container } = render(
    <LaneHeader lane={makeLane(expanded)} onToggleExpand={() => {}} />,
  );
  return container.querySelector(".tl-lane-head") as HTMLElement;
};

describe("item 5 — collapsed lane shows the title only", () => {
  it("renders the sub-caption node only when expanded", () => {
    const collapsed = renderHead(false);
    expect(collapsed.querySelector(".tl-lane-head__sub")).toBeNull();
    expect(collapsed.querySelector(".tl-lane-head__name")?.textContent).toBe("RMS Loudness");

    const expanded = renderHead(true);
    expect(expanded.querySelector(".tl-lane-head__sub")?.textContent).toBe(
      "essentia · mix + 4 stems",
    );
  });

  it("collapsed-lane height helper returns ≥ the mini strip height", () => {
    expect(collapsedLaneHeight()).toBeGreaterThanOrEqual(COLLAPSED_STRIP_HEIGHT);
  });
});

describe("item 6 — collapse/expand caret keeps a fixed slot", () => {
  it("the row keeps the same layout classes in both states", () => {
    const collapsed = renderHead(false);
    const expanded = renderHead(true);
    expect(collapsed.className).toBe(expanded.className);
    expect(collapsed.className).toContain("tl-lane-head");
  });

  it("the caret is the first child (same flex slot) in both states", () => {
    expect(renderHead(false).firstElementChild?.classList.contains("caret")).toBe(true);
    expect(renderHead(true).firstElementChild?.classList.contains("caret")).toBe(true);
  });

  it("the caret container class + testid are the same; only the glyph differs", () => {
    const cCaret = renderHead(false).querySelector(".caret") as HTMLElement;
    const eCaret = renderHead(true).querySelector(".caret") as HTMLElement;
    expect(cCaret.className).toBe(eCaret.className);
    expect(cCaret.getAttribute("data-testid")).toBe(eCaret.getAttribute("data-testid"));
    expect(cCaret.querySelector("i")?.className).toBe("ph ph-caret-right");
    expect(eCaret.querySelector("i")?.className).toBe("ph ph-caret-down");
  });
});
