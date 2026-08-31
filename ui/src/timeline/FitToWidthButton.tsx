// FitToWidthButton — the footer "fit to width" control (plan item 7 / R3).
//
// Icon-only: a single Phosphor glyph, no text label and no border. It shares
// the `.zic` class with the zoom-in / zoom-out buttons, so it inherits their
// exact hover treatment (transparent → `--color-neutral-900` background, same
// transition-less swap). The action (`fitToWidthPxPerBar`) and the `f`
// keybinding live in `App.tsx` / `keymap.ts` and are unchanged; the button
// keeps its accessible name.

export function FitToWidthButton({
  onClick,
}: {
  onClick: () => void;
}): React.JSX.Element {
  return (
    <button
      type="button"
      className="zic"
      data-testid="fit-to-width"
      aria-label="Fit to width"
      title="Fit to width"
      onClick={onClick}
    >
      <i className="ph ph-arrows-out-line-horizontal" />
    </button>
  );
}
