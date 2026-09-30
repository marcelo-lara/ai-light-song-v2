// useSongSelection.ts — the selected song + its `?song=` deep-link. Split
// out of App.tsx (v3.9 item 7) with no behaviour change.
//
// This is also the entry point the visual-regression suite drives
// (`gotoSong`).

import { useEffect, useState } from "react";

import type { DrawerView } from "./useDrawer";

export function useSongSelection(
  setActiveView: React.Dispatch<React.SetStateAction<DrawerView>>,
): readonly [string | null, React.Dispatch<React.SetStateAction<string | null>>] {
  const [song, setSong] = useState<string | null>(null);

  // Deep-link: `/?song=<name>` selects a song on load, and the current
  // selection is mirrored back into the URL so a reload restores it.
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("song");
    if (initial) {
      setSong(initial);
      setActiveView("timeline");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (song) url.searchParams.set("song", song);
    else url.searchParams.delete("song");
    window.history.replaceState(null, "", url);
  }, [song]);

  return [song, setSong] as const;
}
