// useSongDiscovery.ts — discovers the analysed-song list for the Select Song
// drawer view. Split out of App.tsx (v3.9 item 7) with no behaviour change.

import { useEffect, useState } from "react";

import { discoverSongs } from "../data";
import { selectSongListState, type SongListState } from "./loadStates";

export interface SongDiscoveryState {
  songs: string[];
  discoveryError: string | null;
  discoveryLoaded: boolean;
  songListState: SongListState;
}

export function useSongDiscovery(): SongDiscoveryState {
  const [songs, setSongs] = useState<string[]>([]);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [discoveryLoaded, setDiscoveryLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    discoverSongs()
      .then((result) => {
        if (cancelled) return;
        setSongs(result.songs);
        setDiscoveryError(null);
        setDiscoveryLoaded(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDiscoveryError(error instanceof Error ? error.message : "Discovery failed.");
        setDiscoveryLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const songListState = selectSongListState({
    loaded: discoveryLoaded,
    error: discoveryError,
    songs,
  });

  return { songs, discoveryError, discoveryLoaded, songListState };
}
