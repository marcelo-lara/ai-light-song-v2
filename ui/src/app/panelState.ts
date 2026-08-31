// panelState.ts — the left panel (drawer) open/closed model (plan item 4).
//
// R2: the left panel mounts *collapsed* on first load. Its open/closed state
// persists per session in localStorage, wrapped in try/catch so a private
// window or blocked storage falls back to collapsed (the default) rather than
// breaking the shell. Kept as a pure module so it is unit-testable without
// React / DOM lifecycle (`src/app/panelState.test.ts`).

/** First-load / unreadable-storage default: the panel is collapsed. */
export const DEFAULT_LEFT_PANEL_OPEN = false;

const STORAGE_KEY = "als.ui.leftPanel.v1";

export type LeftPanelAction = "toggle" | "open" | "close";

/** Pure reducer for the left panel open flag. */
export function leftPanelReducer(open: boolean, action: LeftPanelAction): boolean {
  switch (action) {
    case "toggle":
      return !open;
    case "open":
      return true;
    case "close":
      return false;
  }
}

/** Read the persisted open flag; absent or unreadable → collapsed. */
export function loadLeftPanelOpen(): boolean {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (raw == null) return DEFAULT_LEFT_PANEL_OPEN;
    return raw === "true";
  } catch {
    return DEFAULT_LEFT_PANEL_OPEN;
  }
}

/** Persist the open flag. Best-effort — persistence is a convenience. */
export function saveLeftPanelOpen(open: boolean): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, String(open));
  } catch {
    // ignore — private window / blocked storage
  }
}
