import { type Page, expect } from "@playwright/test";

export const FIXTURES = {
  full: "RegFull - Fixture",
  partial: "RegPartial - Fixture",
  noAudio: "_test_song",
} as const;

/**
 * Freeze wall-clock time + randomness and kill every transition/animation, so a
 * screenshot depends only on the code under test. Call before `page.goto`.
 */
export async function injectDeterminism(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const FIXED = new Date("2025-01-01T00:00:00.000Z").getTime();
    const RealDate = Date;
    class FrozenDate extends RealDate {
      constructor(...args: unknown[]) {
        if (args.length === 0) {
          super(FIXED);
        } else {
          // @ts-expect-error variadic passthrough
          super(...args);
        }
      }
      static now() {
        return FIXED;
      }
    }
    // @ts-expect-error override
    window.Date = FrozenDate;

    let seed = 0x2545f4917;
    Math.random = () => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed / 0x7fffffff;
    };

    const css =
      "*,*::before,*::after{transition:none!important;animation:none!important;" +
      "caret-color:transparent!important;scroll-behavior:auto!important}";
    const inject = () => {
      const style = document.createElement("style");
      style.setAttribute("data-injected-determinism", "");
      style.textContent = css;
      document.head.appendChild(style);
    };
    if (document.head) inject();
    else document.addEventListener("DOMContentLoaded", inject);
  });
}

/**
 * Navigate to a song via the `?song=` deep link and wait for the app's own
 * readiness marker plus font readiness — never a bare timeout.
 */
export async function gotoSong(page: Page, name: string): Promise<void> {
  await injectDeterminism(page);
  await page.goto(`/?song=${encodeURIComponent(name)}`);
  await page.waitForSelector('html[data-ui-ready="1"]', { timeout: 20_000 });
  await page.evaluate(() => document.fonts.ready);
}

export interface RuntimeErrorSink {
  list(): string[];
}

/**
 * Collect anything that should never happen on a healthy load: console
 * error/warning, page errors, unhandled rejections, and failed responses for a
 * URL under `/data/analysis/`. `/data/songs/*.mp3` 404s are only tolerated for
 * the no-audio spec (pass `{ allowMissingAudio: true }`).
 */
export function assertNoRuntimeErrors(
  page: Page,
  opts: { allowMissingAudio?: boolean } = {},
): RuntimeErrorSink {
  const problems: string[] = [];

  page.on("console", (msg) => {
    const type = msg.type();
    if (type !== "error" && type !== "warning") return;
    const text = msg.text();
    // Chromium logs a URL-less "Failed to load resource ... 404" console error
    // for the absent mp3; the request/response handlers below still catch any
    // real /data/analysis/ failure (those carry a URL).
    if (opts.allowMissingAudio && /Failed to load resource.*\b(404|ERR_ABORTED)\b/.test(text)) {
      return;
    }
    problems.push(`console.${type}: ${text}`);
  });
  page.on("pageerror", (err) => {
    problems.push(`pageerror: ${err.message}`);
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (opts.allowMissingAudio && /\/data\/songs\/.*\.mp3$/.test(url)) return;
    if (url.includes("/data/analysis/") || url.includes("/data/songs/")) {
      problems.push(`requestfailed: ${url} (${req.failure()?.errorText ?? "?"})`);
    }
  });
  page.on("response", (res) => {
    const url = res.url();
    if (res.status() < 400) return;
    if (opts.allowMissingAudio && /\/data\/songs\/.*\.mp3$/.test(url)) return;
    if (url.includes("/data/analysis/")) {
      problems.push(`response ${res.status()}: ${url}`);
    }
  });

  return { list: () => [...problems] };
}

export interface LaneExtent {
  hasCanvas: boolean;
  /** rightmost non-transparent column, in timeline-content px (0 at content left) */
  lastNonEmptyX: number;
  /** total timeline content width in px */
  contentWidth: number;
}

/**
 * Rightmost non-empty pixel column of a lane's canvas, expressed relative to the
 * timeline content width — for the §5 full-extent assertions.
 */
export async function fullExtentOfLane(
  page: Page,
  laneId: string,
): Promise<LaneExtent> {
  return page.evaluate((id) => {
    const body = document.querySelector(
      `.tl-lane-body[data-lane="${id}"]`,
    ) as HTMLElement | null;
    const grid = document.querySelector(".app-timeline__grid") as HTMLElement | null;
    const canvas = body?.querySelector("canvas") as HTMLCanvasElement | null;
    if (!body || !grid || !canvas) {
      return { hasCanvas: false, lastNonEmptyX: -1, contentWidth: grid?.getBoundingClientRect().width ?? 0 };
    }
    const w = canvas.width;
    const h = canvas.height;
    const ctx = canvas.getContext("2d");
    let lastCol = -1;
    if (ctx && w > 0 && h > 0) {
      const data = ctx.getImageData(0, 0, w, h).data;
      for (let x = w - 1; x >= 0 && lastCol < 0; x--) {
        for (let y = 0; y < h; y++) {
          if (data[(y * w + x) * 4 + 3] !== 0) {
            lastCol = x;
            break;
          }
        }
      }
    }
    const cRect = canvas.getBoundingClientRect();
    const gRect = grid.getBoundingClientRect();
    const cssX = w > 0 ? (lastCol / w) * cRect.width : -1;
    return {
      hasCanvas: true,
      lastNonEmptyX: lastCol < 0 ? -1 : cRect.left - gRect.left + cssX,
      contentWidth: gRect.width,
    };
  }, laneId);
}

/** Re-await the app readiness marker after an interaction that re-lays-out. */
export async function waitReady(page: Page): Promise<void> {
  await page.waitForSelector('html[data-ui-ready="1"]', { timeout: 20_000 });
  await page.evaluate(() => document.fonts.ready);
}

/** Convenience: assert the readiness marker + no runtime errors for a surface. */
export async function expectHealthy(sink: RuntimeErrorSink): Promise<void> {
  expect(sink.list()).toEqual([]);
}
