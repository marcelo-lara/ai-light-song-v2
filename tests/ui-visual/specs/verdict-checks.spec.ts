import fs from "node:fs";
import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.11 item 24 — `verdict_check` cards in the Pending proposals view and the
// read-only "Verdict Checks" lane. `RegFull - Fixture` carries a verdict.json
// (drops refuted 004-005, chorus_is_drop unresolved 007-008 with a pending
// verdict_check, has_build_ups confirmed 010, bpm with no section evidence) and
// a pending.json (one hint, one verdict_check). Confirm / Reject write through
// the real `PUT /api/proposal-decision/<song>` into the writable fixture, so
// both files are snapshotted and restored around every test (same convention as
// hint-drag.spec.ts). If a run is hard-killed:
// `git checkout -- tests/ui-visual/fixtures/analysis`.

const FIXTURE_DIR = path.join(process.cwd(), "fixtures/analysis/RegFull - Fixture");
const VERDICT = path.join(FIXTURE_DIR, "reference/pre-analysis/verdict.json");
const QUEUE = path.join(FIXTURE_DIR, "reference/proposals/pending.json");
const SECTIONS = path.join(FIXTURE_DIR, "sections.json");

let verdictBackup = "";
let queueBackup = "";
test.beforeAll(() => {
  verdictBackup = fs.readFileSync(VERDICT, "utf-8");
  queueBackup = fs.readFileSync(QUEUE, "utf-8");
});
const restore = () => {
  if (verdictBackup) fs.writeFileSync(VERDICT, verdictBackup);
  if (queueBackup) fs.writeFileSync(QUEUE, queueBackup);
};
test.afterEach(restore);
test.afterAll(restore);

const LANE = '.tl-lane-body[data-lane="verdictChecks"]';
const CHECK_ID = "prop-check-001";

const readJson = (file: string) => JSON.parse(fs.readFileSync(file, "utf-8"));

/** Verdict rows whose first-pass evidence names sections, with their section indices (sections.json order). */
function evidenceRows(): { field: string; first: number; last: number }[] {
  const verdict = readJson(VERDICT);
  const sections = readJson(SECTIONS);
  const rows: { section_id: string }[] = Array.isArray(sections) ? sections : sections.sections;
  const out: { field: string; first: number; last: number }[] = [];
  for (const [field, row] of Object.entries(verdict.verdicts.fields) as [string, { evidence: Record<string, unknown> }][]) {
    const idx: number[] = [];
    for (const [key, ids] of Object.entries(row.evidence)) {
      if (!key.endsWith("_section_ids") || !Array.isArray(ids)) continue;
      for (const id of ids as string[]) idx.push(rows.findIndex((s) => s.section_id === id));
    }
    if (idx.length) out.push({ field, first: Math.min(...idx), last: Math.max(...idx) });
  }
  return out;
}

async function expandLane(page: Page, laneId: string): Promise<void> {
  const caret = page.getByTestId(`lane-collapse-${laneId}`);
  if ((await caret.getAttribute("aria-expanded")) !== "true") await caret.click();
  await waitReady(page);
}

/** Filled column runs (edges + a sampled interior RGBA) of the lane canvas, in lane-local CSS px. */
async function blockRuns(page: Page, laneSel: string) {
  return page.evaluate((sel) => {
    const canvas = document.querySelector(`${sel} canvas`) as HTMLCanvasElement | null;
    if (!canvas) return [];
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return [];
    const w = canvas.width;
    const h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    const k = (canvas.getBoundingClientRect().width || w) / w;
    const filled = (x: number) => {
      for (let y = 0; y < h; y++) if (data[(y * w + x) * 4 + 3] !== 0) return true;
      return false;
    };
    const runs: { x1: number; x2: number; rgba: string }[] = [];
    let s = -1;
    const close = (end: number) => {
      const mid = Math.round((s + end) / 2);
      let y = 0;
      for (; y < h; y++) if (data[(y * w + mid) * 4 + 3] !== 0) break;
      const i = ((y + 3) * w + mid) * 4;
      runs.push({ x1: s * k, x2: (end + 1) * k, rgba: `${data[i]},${data[i + 1]},${data[i + 2]},${data[i + 3]}` });
    };
    for (let x = 0; x < w; x++) {
      const f = filled(x);
      if (f && s < 0) s = x;
      if (!f && s >= 0) {
        close(x - 1);
        s = -1;
      }
    }
    if (s >= 0) close(w - 1);
    return runs.filter((r) => r.x2 - r.x1 > 3);
  }, laneSel);
}

/** Left/right edge (timeline px) of sections `first`..`last`. The Segments row insets every block's right edge by a 2 px gap (`buildSegments`), added back here. */
async function sectionSpan(page: Page, first: number, last: number) {
  return page.evaluate(
    ([a, b]) => {
      const blocks = Array.from(document.querySelectorAll(".tl-seg-block")) as HTMLElement[];
      const left = parseFloat(blocks[a]!.style.left);
      const lastBlock = blocks[b]!;
      return { x1: left, x2: parseFloat(lastBlock.style.left) + parseFloat(lastBlock.style.width) + 2 };
    },
    [first, last],
  );
}

async function clickLaneAt(page: Page, laneId: string, localX: number): Promise<void> {
  await page.locator(`.tl-lane-head[data-lane="${laneId}"]`).scrollIntoViewIfNeeded();
  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(`.tl-lane-body[data-lane="${laneId}"] .tl-canvas-lane`).boundingBox();
  if (!rect) throw new Error(`${laneId} lane container not found`);
  await page.mouse.click(rect.x + localX, rect.y + rect.height / 2);
}

const clockText = async (page: Page) => (await page.locator(".app-header__time").first().innerText()).trim();

async function openPendingView(page: Page): Promise<void> {
  await page.getByTestId("burger-toggle").click();
  await page.getByRole("button", { name: "Pending proposals", exact: true }).click();
  await expect(page.getByTestId("pending-proposals")).toBeVisible();
}

const verdictCard = (page: Page) => page.locator('[data-proposal-type="verdict_check"]');

test.describe("v3.11 item 24 — Verdict Checks lane", () => {
  test("exactly one lane; one block per row with section evidence; edges on the evidence sections; one tint per outcome", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);

    const head = page.locator('.tl-lane-head[data-lane="verdictChecks"]');
    await expect(head).toHaveCount(1);
    await expect(head.locator(".tl-lane-head__name-text")).toHaveText("Verdict Checks");
    // read-only, not an experiment: no flask badge
    await expect(head.locator(".tl-lane-head__flask")).toHaveCount(0);

    await expandLane(page, "verdictChecks");
    const expected = evidenceRows();
    expect(expected.length).toBeGreaterThan(0);
    // the bpm row has no section evidence, so rows > blocks
    expect(Object.keys(readJson(VERDICT).verdicts.fields).length).toBeGreaterThan(expected.length);

    await expect.poll(async () => (await blockRuns(page, LANE)).length).toBe(expected.length);
    const runs = await blockRuns(page, LANE);
    const ordered = [...expected].sort((a, b) => a.first - b.first);
    for (const [i, row] of ordered.entries()) {
      const span = await sectionSpan(page, row.first, row.last);
      expect(Math.abs(runs[i]!.x1 - span.x1), `${row.field} left edge`).toBeLessThanOrEqual(2);
      expect(Math.abs(runs[i]!.x2 - span.x2), `${row.field} right edge`).toBeLessThanOrEqual(2);
    }
    // three outcomes -> three distinct tints
    expect(new Set(runs.map((r) => r.rgba)).size).toBe(3);

    // the lane's canvas spans the whole timeline
    const widths = await page.evaluate((sel) => {
      const body = document.querySelector(sel) as HTMLElement;
      const canvas = body.querySelector("canvas") as HTMLCanvasElement;
      return { body: body.getBoundingClientRect().width, canvas: parseFloat(canvas.style.width) };
    }, LANE);
    expect(Math.abs(widths.body - widths.canvas)).toBeLessThanOrEqual(1);

    await expectHealthy(errors);
  });

  for (const [label, fixture] of [
    ["RegPartial", FIXTURES.partial],
    ["_test_song", FIXTURES.noAudio],
  ] as const) {
    test(`${label} has no verdict.json: no Verdict Checks lane and no empty header`, async ({ page }) => {
      const errors = assertNoRuntimeErrors(page, { allowMissingAudio: fixture === FIXTURES.noAudio });
      await gotoSong(page, fixture);
      await waitReady(page);
      await expect(page.locator('[data-lane="verdictChecks"]')).toHaveCount(0);
      await expect(page.getByText("Verdict Checks")).toHaveCount(0);
      // RegPartial deliberately lacks the per-stem FFT files (the degraded-
      // banner fixture); only verdict/queue-related failures matter here.
      expect(errors.list().filter((e) => !/fft_bands/.test(e))).toEqual([]);
    });
  }

  test("a block with a pending verdict_check seeks and opens the Pending proposals view on that card", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await expandLane(page, "verdictChecks");
    const runs = await blockRuns(page, LANE);
    // blocks left to right: drops (44.78), chorus_is_drop (96.48), has_build_ups (155.54)
    await clickLaneAt(page, "verdictChecks", (runs[1]!.x1 + runs[1]!.x2) / 2);
    await expect.poll(() => clockText(page)).toBe("1:36.5");
    await expect(page.getByTestId("pending-proposals")).toBeVisible();
    await expect(verdictCard(page)).toHaveClass(/review-queue__q--focused/);
    await expectHealthy(errors);
  });

  test("a block without a pending verdict_check only seeks", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await expandLane(page, "verdictChecks");
    const runs = await blockRuns(page, LANE);
    await clickLaneAt(page, "verdictChecks", (runs[0]!.x1 + runs[0]!.x2) / 2);
    await expect.poll(() => clockText(page)).toBe("0:44.8");
    await expect(page.getByTestId("pending-proposals")).toHaveCount(0);
    await expect(page.locator(".app-rightpanel")).toHaveCount(0);
    await expectHealthy(errors);
  });

  test("the LLM Pending Proposals lane counts pending hint rows only", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await expandLane(page, "llmPendingProposals");
    const hints = readJson(QUEUE).proposals.filter(
      (p: { type: string; status: string }) => p.type === "hint" && p.status === "pending",
    ).length;
    expect(readJson(QUEUE).proposals.length).toBeGreaterThan(hints); // a verdict_check is in the file
    await expect
      .poll(async () => (await blockRuns(page, '.tl-lane-body[data-lane="llmPendingProposals"]')).length)
      .toBe(hints);
    const w = await page.evaluate(() => {
      const body = document.querySelector('.tl-lane-body[data-lane="llmPendingProposals"]') as HTMLElement;
      const canvas = body.querySelector("canvas") as HTMLCanvasElement;
      return { body: body.getBoundingClientRect().width, canvas: parseFloat(canvas.style.width) };
    });
    expect(Math.abs(w.body - w.canvas)).toBeLessThanOrEqual(1);
    await expectHealthy(errors);
  });
});

test.describe("v3.11 item 24 — verdict_check card", () => {
  test("one hint and one verdict_check: two cards; the check shows its heading, five evidence rows, the question, enabled Confirm / Reject", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await openPendingView(page);

    await expect(page.getByTestId("pending-proposal-card")).toHaveCount(2);
    const card = verdictCard(page);
    await expect(card).toHaveCount(1);
    const check = readJson(QUEUE).proposals.find((p: { id: string }) => p.id === CHECK_ID).verdict_check;
    await expect(card.getByTestId("verdict-check-claim")).toHaveText(check.claim);
    await expect(card.locator("[data-evidence-kind]")).toHaveCount(5);
    await expect(card.getByTestId("verdict-check-question")).toHaveText(check.question);
    await expect(card.getByRole("button", { name: "Confirm", exact: true })).toBeEnabled();
    await expect(card.getByRole("button", { name: "Reject", exact: true })).toBeEnabled();

    await expect(card).toHaveScreenshot("verdict-check-card.png");
    await expectHealthy(errors);
  });

  test("Reject without a reason is refused and the card stays", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await openPendingView(page);
    const card = verdictCard(page);
    await card.getByRole("button", { name: "Reject", exact: true }).click();
    await expect(card.getByRole("button", { name: "Confirm reject" })).toBeDisabled();
    await card.locator("textarea").fill("   ");
    await expect(card.getByRole("button", { name: "Confirm reject" })).toBeDisabled();
    await expect(page.getByTestId("pending-proposal-card")).toHaveCount(2);
    expect(readJson(VERDICT).second_pass.fields.chorus_is_drop.operator).toBeNull();
    await expectHealthy(errors);
  });

  test("Confirm: the card leaves the queue and the verdict's operator is confirmed", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await openPendingView(page);
    await verdictCard(page).getByRole("button", { name: "Confirm", exact: true }).click();
    await expect(verdictCard(page)).toHaveCount(0);
    await expect(page.getByTestId("pending-proposal-card")).toHaveCount(1);

    const entry = readJson(VERDICT).second_pass.fields.chorus_is_drop;
    expect(entry.operator).toEqual({ answer: "confirmed", reason: null, check_id: CHECK_ID });
    // the rest of the entry is untouched
    expect(entry.verdict).toBeNull();
    const row = readJson(QUEUE).proposals.find((p: { id: string }) => p.id === CHECK_ID);
    expect(row.status).toBe("approved");
    expect(row.rejection_reason).toBeNull();
    // the hint card is still pending
    expect(readJson(QUEUE).proposals.find((p: { id: string }) => p.id === "prop-hint-001").status).toBe("pending");
    await expectHealthy(errors);
  });

  test("Reject with a reason is kept on the verdict and the queue row", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await openPendingView(page);
    const card = verdictCard(page);
    await card.getByRole("button", { name: "Reject", exact: true }).click();
    await card.locator("textarea").fill("the chorus is not the drop");
    await card.getByRole("button", { name: "Confirm reject" }).click();
    await expect(verdictCard(page)).toHaveCount(0);

    expect(readJson(VERDICT).second_pass.fields.chorus_is_drop.operator).toEqual({
      answer: "rejected",
      reason: "the chorus is not the drop",
      check_id: CHECK_ID,
    });
    const row = readJson(QUEUE).proposals.find((p: { id: string }) => p.id === CHECK_ID);
    expect(row.status).toBe("rejected");
    expect(row.rejection_reason).toBe("the chorus is not the drop");
    await expectHealthy(errors);
  });
});
