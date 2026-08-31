import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LEFT_PANEL_OPEN,
  leftPanelReducer,
  loadLeftPanelOpen,
  saveLeftPanelOpen,
} from "./panelState";

describe("leftPanelReducer", () => {
  it("defaults to collapsed", () => {
    expect(DEFAULT_LEFT_PANEL_OPEN).toBe(false);
  });

  it("toggle / open / close", () => {
    expect(leftPanelReducer(false, "toggle")).toBe(true);
    expect(leftPanelReducer(true, "toggle")).toBe(false);
    expect(leftPanelReducer(false, "open")).toBe(true);
    expect(leftPanelReducer(true, "close")).toBe(false);
  });
});

describe("left panel persistence", () => {
  beforeEach(() => {
    globalThis.localStorage?.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    globalThis.localStorage?.clear();
  });

  it("absent value → collapsed", () => {
    expect(loadLeftPanelOpen()).toBe(false);
  });

  it("round-trips open then closed", () => {
    saveLeftPanelOpen(true);
    expect(loadLeftPanelOpen()).toBe(true);
    saveLeftPanelOpen(false);
    expect(loadLeftPanelOpen()).toBe(false);
  });

  it("unreadable storage → collapsed", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(loadLeftPanelOpen()).toBe(false);
  });
});
