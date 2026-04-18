import { useEffect, useRef } from "preact/hooks";

const CARD_WIDTH = 420;
const VIEWPORT_MARGIN = 16;
const VERTICAL_OFFSET = 14;

function resolvePosition(anchorPosition) {
  if (!anchorPosition) {
    return { top: VIEWPORT_MARGIN, left: VIEWPORT_MARGIN };
  }

  const viewportWidth = window.innerWidth || CARD_WIDTH;
  const viewportHeight = window.innerHeight || 640;
  const availableWidth = Math.max(viewportWidth - (VIEWPORT_MARGIN * 2), 280);
  const cardWidth = Math.min(CARD_WIDTH, availableWidth);
  const prefersLeftSide = anchorPosition.x + cardWidth + VIEWPORT_MARGIN > viewportWidth;
  const left = prefersLeftSide
    ? Math.max(VIEWPORT_MARGIN, anchorPosition.x - cardWidth - VIEWPORT_MARGIN)
    : Math.min(anchorPosition.x + VIEWPORT_MARGIN, viewportWidth - cardWidth - VIEWPORT_MARGIN);
  const top = Math.min(
    Math.max(anchorPosition.y + VERTICAL_OFFSET, VIEWPORT_MARGIN),
    Math.max(VIEWPORT_MARGIN, viewportHeight - 320),
  );

  return { top, left };
}

export default function OverlayPanel({ isOpen, title, subtitle, anchorPosition, onClose, children }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    function handlePointerDown(event) {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("pointerdown", handlePointerDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const position = resolvePosition(anchorPosition);

  return (
    <section
      className="overlay-panel hovercard-panel"
      ref={panelRef}
      role="dialog"
      aria-label={title}
      style={{ top: `${position.top}px`, left: `${position.left}px` }}
    >
        <div className="overlay-panel-header">
          <div>
            <p className="eyebrow">Lane Item</p>
            <h2>{title}</h2>
            {subtitle ? <p className="overlay-panel-subtitle">{subtitle}</p> : null}
          </div>
          <button type="button" className="overlay-close-button secondary-button" onClick={onClose} aria-label="Close detail overlay">
            Close
          </button>
        </div>
        <div className="overlay-panel-body">{children}</div>
    </section>
  );
}