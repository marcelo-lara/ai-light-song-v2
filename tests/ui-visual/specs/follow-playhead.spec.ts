import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// Plan v1.5 item 6 (R6): a footer toggle, immediately left of the `Lanes`
// button, follows the playhead while playing. It defaults on, persists per
// session, and turns itself off when the user scrolls during playback. The
// suite cannot press Play (see "Conventions for every item"), so the
// behavioural half is covered by `followScrollLeft` + `isUserScroll` in
// `ui/src/timeline/follow.test.ts`; here we assert placement, the default,
// toggling, the visible pressed state and persistence.

test("item 6 — follow-playhead toggle", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);

  // One-time clear — NOT an addInitScript, which would re-run on the reload in
  // step 6 and wipe the just-persisted flag, making persistence unobservable.
  await page.goto("/");
  await page.evaluate(() => {
    try {
      localStorage.clear();
    } catch {
      /* private window / blocked storage */
    }
  });
  await gotoSong(page, FIXTURES.full);

  // 1. runtime assertions clean (re-checked at the end).

  // 2. placement — the follow toggle sits to the left of the `Lanes` button.
  const follow = page.getByTestId("follow-toggle");
  await expect(follow).toHaveCount(1);
  const lanesBtn = page.getByRole("button", { name: "Lanes" });
  const followBox = await follow.boundingBox();
  const lanesBox = await lanesBtn.boundingBox();
  if (!followBox || !lanesBox) throw new Error("footer buttons not found");
  expect(followBox.x + followBox.width).toBeLessThan(lanesBox.x);

  // 3. default on.
  await expect(follow).toHaveAttribute("aria-pressed", "true");

  // 4. paused, nothing follows. Press "To start" (scrollLeft → 0), then seek to
  // hint-003 (64.0 s) via its stacked event card — `followScrollLeft` returns
  // the current offset while paused, so the timeline must not move.
  await page.getByRole("button", { name: "To start" }).click();
  await waitReady(page);
  const viewport = page.getByTestId("timeline-viewport");
  expect(await viewport.evaluate((el) => el.scrollLeft)).toBe(0);

  await page.getByTestId("lane-events-humanHints").click();
  await page.getByTestId("lane-event-hint-003").click();
  await expect(page.locator(".app-header__time")).toHaveText("1:04.0");
  expect(await viewport.evaluate((el) => el.scrollLeft)).toBe(0);

  // 5. toggling — `aria-pressed` and the pressed styling both change. Move the
  // pointer off the button before reading `color` so a lingering `:hover` does
  // not mask the pressed-state difference.
  const colorOf = async () => {
    await page.mouse.move(2, 2);
    return follow.evaluate((el) => getComputedStyle(el).color);
  };
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const offColor = await colorOf();
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  const onColor = await colorOf();
  expect(offColor).not.toBe(onColor);

  // 6. persistence — turn off, reload, still off. Then reset to the default.
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await page.reload();
  await waitReady(page);
  await expect(page.getByTestId("follow-toggle")).toHaveAttribute("aria-pressed", "false");

  // 7. baseline — follow off, transport paused. Not generated here; the
  // orchestrator runs `--update-snapshots`.
  await expect(page.locator(".app-footer")).toHaveScreenshot("footer-follow.png");

  await page.evaluate(() => {
    try {
      window.localStorage.clear();
    } catch {
      /* ignore */
    }
  });

  expect(errors.list()).toEqual([]);
});
