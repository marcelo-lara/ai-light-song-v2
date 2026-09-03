import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LEFT_PANEL_OPEN,
  leftPanelReducer,
  loadLeftPanelOpen,
  saveLeftPanelOpen,
  shouldDismissLeftPanel,
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

describe("shouldDismissLeftPanel", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  function mount(): { drawerChild: Element; burgerChild: Element; outside: Element } {
    document.body.innerHTML = `
      <div data-testid="left-panel"><button id="drawer-entry">Timeline</button></div>
      <button data-testid="burger-toggle"><i id="burger-icon"></i></button>
      <div id="elsewhere"><span id="deep">x</span></div>
    `;
    return {
      drawerChild: document.getElementById("drawer-entry")!,
      burgerChild: document.getElementById("burger-icon")!,
      outside: document.getElementById("deep")!,
    };
  }

  it("target inside the drawer → false", () => {
    const { drawerChild } = mount();
    expect(shouldDismissLeftPanel(true, drawerChild)).toBe(false);
  });

  it("target inside the burger → false", () => {
    const { burgerChild } = mount();
    expect(shouldDismissLeftPanel(true, burgerChild)).toBe(false);
  });

  it("target elsewhere → true", () => {
    const { outside } = mount();
    expect(shouldDismissLeftPanel(true, outside)).toBe(true);
  });

  it("open === false → false", () => {
    const { outside } = mount();
    expect(shouldDismissLeftPanel(false, outside)).toBe(false);
  });

  it("target === null → false", () => {
    expect(shouldDismissLeftPanel(true, null)).toBe(false);
  });
});
