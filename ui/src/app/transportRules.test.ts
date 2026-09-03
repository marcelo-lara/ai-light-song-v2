import { describe, expect, it } from "vitest";

import { seekTimeForCardClick } from "./transportRules";

describe("seekTimeForCardClick", () => {
  it("returns null while playing (R3: do not move the playhead)", () => {
    expect(seekTimeForCardClick(true, 52)).toBeNull();
  });

  it("returns the click time while paused", () => {
    expect(seekTimeForCardClick(false, 52)).toBe(52);
  });

  it("returns 0 (not null) for a click at time 0 while paused", () => {
    expect(seekTimeForCardClick(false, 0)).toBe(0);
  });
});
