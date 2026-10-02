// useDrawer.ts — the left-panel (drawer) open/closed + active-view state.
// Split out of App.tsx (v3.9 item 7) with no behaviour change.

import { useEffect, useRef, useState } from "react";

import { loadLeftPanelOpen, saveLeftPanelOpen, shouldDismissLeftPanel } from "./panelState";

export type DrawerView = "song" | "timeline" | "inspector" | "review" | "proposals";

export interface DrawerEntry {
  id: DrawerView;
  label: string;
  icon: string;
}

export const DRAWER_ENTRIES: readonly DrawerEntry[] = [
  { id: "song", label: "Select Song", icon: "ph-file-audio" },
  { id: "timeline", label: "Timeline", icon: "ph-waveform" },
  { id: "inspector", label: "Artifact inspector", icon: "ph-squares-four" },
  { id: "review", label: "Review queue", icon: "ph-flag" },
  // v3.7 item 11 — MCP correction proposals (propose_hint), queued for human approve/reject.
  { id: "proposals", label: "Pending proposals", icon: "ph-inbox" },
] as const;

export interface DrawerState {
  drawerOpen: boolean;
  setDrawerOpen: React.Dispatch<React.SetStateAction<boolean>>;
  activeView: DrawerView;
  setActiveView: React.Dispatch<React.SetStateAction<DrawerView>>;
  drawerRef: React.RefObject<HTMLElement>;
}

export function useDrawer(): DrawerState {
  // Left panel (drawer): collapsed by default on first load (plan item 4 / R2),
  // open/closed persisted per session.
  const [drawerOpen, setDrawerOpen] = useState(loadLeftPanelOpen);
  const [activeView, setActiveView] = useState<DrawerView>("timeline");
  const drawerRef = useRef<HTMLElement>(null);
  const drawerWasOpen = useRef(drawerOpen);

  // Persist the left panel open/closed state (plan item 4).
  useEffect(() => {
    saveLeftPanelOpen(drawerOpen);
  }, [drawerOpen]);

  // R5 (plan v1.5 item 2): while the drawer is open, a mousedown anywhere
  // outside it (and outside the burger) closes it. `mousedown`, not `click`,
  // matches RightPanel's dismissal so a drag that starts outside also closes.
  // Registered only while open; removed on cleanup.
  useEffect(() => {
    if (!drawerOpen) return;
    const onPointer = (event: MouseEvent): void => {
      if (shouldDismissLeftPanel(true, event.target as Element | null)) {
        setDrawerOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [drawerOpen]);

  // Move focus into the drawer when it opens (non-modal — no trap).
  useEffect(() => {
    // only on an open transition (not initial mount) so we don't grab focus
    // out from under the page on load.
    if (drawerOpen && !drawerWasOpen.current) {
      drawerRef.current?.querySelector<HTMLElement>(".dr-item")?.focus();
    }
    drawerWasOpen.current = drawerOpen;
  }, [drawerOpen]);

  return { drawerOpen, setDrawerOpen, activeView, setActiveView, drawerRef };
}
