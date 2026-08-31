import { useEffect } from "preact/hooks";

export function useTimelineKeyboardShortcuts({ onPlayPause, onPreviousBar, onPreviousBeat, onNextBeat, onNextBar }) {
  useEffect(() => {
    function handleWindowKeyDown(event) {
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName))) {
        return;
      }
      if (event.key === " " || event.code === "Space") {
        event.preventDefault();
        onPlayPause?.();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        event.shiftKey ? onPreviousBar?.() : onPreviousBeat?.();
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        event.shiftKey ? onNextBar?.() : onNextBeat?.();
      }
    }

    window.addEventListener("keydown", handleWindowKeyDown);
    return () => window.removeEventListener("keydown", handleWindowKeyDown);
  }, [onNextBar, onNextBeat, onPlayPause, onPreviousBar, onPreviousBeat]);
}