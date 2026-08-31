import { useEffect } from "preact/hooks";

const DRAG_CLICK_SUPPRESS_MS = 120;

export function useTimelineDragPan({ dragStateRef, scrollerRef, suppressClickRef }) {
  useEffect(() => {
    function handleWindowMouseMove(event) {
      const scrollerElement = scrollerRef.current;
      const dragState = dragStateRef.current;
      if (!dragState.active || !scrollerElement) {
        return;
      }
      const deltaX = event.clientX - dragState.startClientX;
      if (Math.abs(deltaX) > 3) {
        dragState.moved = true;
      }
      if (!dragState.moved) {
        return;
      }
      scrollerElement.scrollLeft = dragState.startScrollLeft - deltaX;
      event.preventDefault();
    }

    function stopDragging() {
      const dragState = dragStateRef.current;
      if (!dragState.active) {
        return;
      }
      if (dragState.moved) {
        suppressClickRef.current = Date.now() + DRAG_CLICK_SUPPRESS_MS;
      }
      Object.assign(dragState, { active: false, startClientX: 0, startScrollLeft: 0, moved: false });
      scrollerRef.current?.classList.remove("is-dragging");
    }

    window.addEventListener("mousemove", handleWindowMouseMove);
    window.addEventListener("mouseup", stopDragging);
    return () => {
      window.removeEventListener("mousemove", handleWindowMouseMove);
      window.removeEventListener("mouseup", stopDragging);
    };
  }, [dragStateRef, scrollerRef, suppressClickRef]);
}