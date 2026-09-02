import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// Item 6 (R5): the collapse/expand caret keeps the same x/y in both states —
// toggling a lane must not move its bounding box. Checked for a canvas lane
// (fftBands) and a sparse lane (sections).

for (const laneId of ["fftBands", "sections"]) {
  test(`item 6 — ${laneId} caret bounding box is stable across toggles`, async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);

    const head = page.locator(`.tl-lane-head[data-lane="${laneId}"]`);
    const caret = page.getByTestId(`lane-collapse-${laneId}`);
    const bbox = async () => {
      const b = await caret.boundingBox();
      return { x: b!.x, y: b!.y };
    };

    const start = await bbox();
    const startCollapsed = await head.getAttribute("data-lane-collapsed");

    // toggle once
    await caret.click();
    await expect(head).not.toHaveAttribute(
      "data-lane-collapsed",
      startCollapsed as string,
    );
    await waitReady(page);
    const toggled = await bbox();
    expect(Math.abs(toggled.x - start.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(toggled.y - start.y)).toBeLessThanOrEqual(1);

    // toggle back
    await caret.click();
    await expect(head).toHaveAttribute(
      "data-lane-collapsed",
      startCollapsed as string,
    );
    await waitReady(page);
    const restored = await bbox();
    expect(Math.abs(restored.x - start.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(restored.y - start.y)).toBeLessThanOrEqual(1);

    expect(errors.list()).toEqual([]);
  });
}
