import { useState } from "preact/hooks";

export function useTimelineSongMenu(onHeaderSongSelect) {
  const [songMenuAnchor, setSongMenuAnchor] = useState(null);
  return {
    songMenuAnchor,
    songMenuOpen: Boolean(songMenuAnchor),
    handleOpenSongMenu(event) { setSongMenuAnchor(event.currentTarget); },
    handleCloseSongMenu() { setSongMenuAnchor(null); },
    async handleSongMenuSelect(song) {
      setSongMenuAnchor(null);
      await onHeaderSongSelect?.(song);
    },
  };
}