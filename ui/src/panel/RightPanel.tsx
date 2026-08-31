// RightPanel.tsx — the 296px `sc-if panelOpen` right panel shell (design §4).
//
// One shell, three modes: block inspector (read-only), hint editor, review
// queue (item 7). This component owns only the chrome — header row / body /
// footer slots, mount-on-`open`, `esc`-to-close and outside-click dismiss
// (clicks on a lane block or a hint pill are ignored so opening the panel
// doesn't immediately close it). Mode content is passed in as `header` /
// `children` / `footer`.

import { useEffect, useRef } from "react";

import { useFocusTrap } from "../app/useFocusTrap";

export type PanelMode = "inspector" | "hint" | "review";

interface RightPanelProps {
  open: boolean;
  onClose: () => void;
  /** left side of the header row (kicker, prev/next, …) */
  header: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  "aria-label"?: string;
}

/** Selectors whose clicks must NOT dismiss the panel (they open/drive it). */
const IGNORE_OUTSIDE =
  ".tl-seg-block, .tl-hint-pill, [data-block-hit], .app-rightpanel, .app-timeline__lane-body";

export function RightPanel({
  open,
  onClose,
  header,
  children,
  footer,
  "aria-label": ariaLabel = "Detail panel",
}: RightPanelProps): React.JSX.Element | null {
  const ref = useRef<HTMLElement>(null);

  // Focus trap + restore-on-close (plan item 10). The panel is the app's one
  // modal surface; while open, Tab stays inside it and closing returns focus
  // to the control that opened it (a lane block, a hint pill, a drawer entry).
  useFocusTrap(ref, open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    const onPointer = (e: MouseEvent): void => {
      const target = e.target as Element | null;
      if (!target) return;
      if (ref.current?.contains(target)) return;
      if (target.closest(IGNORE_OUTSIDE)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    // `mousedown` so a drag that starts outside also dismisses.
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <aside
      className="app-rightpanel app-rightpanel--modal"
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      ref={ref}
    >
      <div className="app-rightpanel__header">
        <div className="app-rightpanel__header-main">{header}</div>
        <button type="button" className="tp" aria-label="Close panel" onClick={onClose}>
          <i className="ph ph-x" />
        </button>
      </div>
      <div className="app-rightpanel__body">{children}</div>
      {footer && <div className="app-rightpanel__footer">{footer}</div>}
    </aside>
  );
}
