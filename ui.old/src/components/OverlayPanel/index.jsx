import { useRef } from "preact/hooks";

import { resolvePosition } from "./resolvePosition.js";
import { useOverlayDismiss } from "./useOverlayDismiss.js";

export default function OverlayPanel({ isOpen, title, subtitle, anchorPosition, onClose, children }) {
  const panelRef = useRef(null);
  useOverlayDismiss({ isOpen, onClose, panelRef });

  if (!isOpen) {
    return null;
  }

  const position = resolvePosition(anchorPosition);

  return (
    <section className="overlay-panel hovercard-panel" ref={panelRef} role="dialog" aria-label={title} style={{ top: `${position.top}px`, left: `${position.left}px` }}>
      <div className="overlay-panel-header">
        <div><p className="eyebrow">Lane Item</p><h2>{title}</h2>{subtitle ? <p className="overlay-panel-subtitle">{subtitle}</p> : null}</div>
        <button type="button" className="overlay-close-button secondary-button" onClick={onClose} aria-label="Close detail overlay">Close</button>
      </div>
      <div className="overlay-panel-body">{children}</div>
    </section>
  );
}