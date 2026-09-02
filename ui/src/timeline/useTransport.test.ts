import { describe, expect, it } from "vitest";

import beatsFixture from "../data/__fixtures__/beats.json";
import { parseBeats } from "../data/parsers";

import { makeCoords } from "./coords";
import { nextBarTime, nextBeatTime } from "./useTransport";

// Real beats.json entries (the _test_song fixture): 6 beats across 2 bars.
const beats = parseBeats(beatsFixture);
const coords = makeCoords({ beats, duration: 3, pxPerBar: 62 });

describe("nextBeatTime — lands on the right beats.json entry", () => {
  it("steps forward to the next beat", () => {
    // playhead just after beat index 1 (t=0.52) -> next is index 2 (t=0.98)
    expect(nextBeatTime(beats, 0.55, 1)).toBeCloseTo(beats[2]!.time);
    expect(beats[2]).toMatchObject({ bar: 1, beat: 3 });
  });

  it("steps backward to the previous beat", () => {
    // playhead at beat index 3 (t=1.44) -> previous is index 2 (t=0.98)
    expect(nextBeatTime(beats, 1.44, -1)).toBeCloseTo(beats[2]!.time);
  });

  it("clamps at the ends", () => {
    expect(nextBeatTime(beats, 0, -1)).toBeCloseTo(beats[0]!.time);
    expect(nextBeatTime(beats, 99, 1)).toBeCloseTo(beats.at(-1)!.time);
  });

  it("crosses the bar boundary and does not stall (ui-issues finding 6)", () => {
    // last beat of bar 1 -> first beat of bar 2. Stepping forward from exactly
    // the last-of-bar-1 time must advance across the boundary, not snap back.
    const lastOfBar1 = beats.findIndex(
      (b, i) => b.bar === 1 && beats[i + 1]?.bar === 2,
    );
    expect(lastOfBar1).toBeGreaterThan(0);
    const a = beats[lastOfBar1]!;
    const b = beats[lastOfBar1 + 1]!;
    expect(b.bar).toBe(2);
    expect(nextBeatTime(beats, a.time, 1)).toBeCloseTo(b.time);
    expect(nextBeatTime(beats, b.time, -1)).toBeCloseTo(a.time);
  });

  it("returns null with no beats", () => {
    expect(nextBeatTime([], 1, 1)).toBeNull();
  });
});

describe("nextBarTime — lands on a real bar-line time", () => {
  const barTimes = coords.barLines.map((l) => l.time);

  it("bar 1 starts at the first downbeat (0.06), bar 2 at 1.9", () => {
    expect(barTimes[0]).toBeCloseTo(0.06);
    expect(barTimes[1]).toBeCloseTo(1.9);
  });

  it("steps forward to the next bar line", () => {
    expect(nextBarTime(coords.barLines, 0.5, 1)).toBeCloseTo(1.9);
  });

  it("steps backward to the previous bar line", () => {
    expect(nextBarTime(coords.barLines, 2.4, -1)).toBeCloseTo(1.9);
  });

  it("does not snap to the bar line the playhead sits on", () => {
    expect(nextBarTime(coords.barLines, 1.9, -1)).toBeCloseTo(0.06);
  });

  it("returns null with no bar lines", () => {
    expect(nextBarTime([], 1, 1)).toBeNull();
  });
});
