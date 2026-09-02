// keymap.ts — the pure keyboard model (plan item 10, refinement §10).
//
// A key event is resolved to a `KeyAction` (or `null` — "not a shortcut") by
// `resolveKeyAction`. It is deliberately free of React / DOM-lifecycle concerns
// so it can be unit-tested directly (`src/app/keymap.test.ts`). `App.tsx` owns
// the single `window` listener and maps each action onto the transport / zoom /
// panel handlers.
//
// Refinement §10 lists the bindings as:
//   space / ←→ / shift+←→ / `+ - [ ]` / `f` / `esc`
// and groups "`+` / `-` / `[` / `]` = zoom" without splitting the four. We map
// them as two zoom pairs (documented deviation, see README.HELPER_UI.md):
//   `+` `=` `]`  → zoom in
//   `-` `_` `[`  → zoom out
// (`=` and `_` are the unshifted faces of `+` and `_`; `[` `]` follow the
// bracket direction.) Plan item 10's "likely prev/next section" guess for
// `[` `]` is NOT taken — §10's explicit word is "zoom".

export type KeyAction =
  | "playPause"
  | "stepBeatBack"
  | "stepBeatForward"
  | "stepBarBack"
  | "stepBarForward"
  | "zoomIn"
  | "zoomOut"
  | "fitToWidth"
  | "closeOverlay";

/** The shape `resolveKeyAction` needs — a real `KeyboardEvent` satisfies it. */
export interface KeyEventLike {
  key: string;
  shiftKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  target?: unknown;
}

const EDITABLE_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/**
 * True when the event originates inside a text-entry control, where the
 * shortcuts must yield to normal typing / caret movement. Duck-typed so unit
 * tests can pass a `{ tagName, isContentEditable }` stub as well as a real node.
 */
export function isEditableTarget(target: unknown): boolean {
  if (!target || typeof target !== "object") return false;
  const el = target as { tagName?: unknown; isContentEditable?: unknown };
  if (el.isContentEditable === true) return true;
  return typeof el.tagName === "string" && EDITABLE_TAGS.has(el.tagName);
}

/**
 * Resolve a key event to a timeline action, or `null` when it is not a
 * shortcut / must be ignored.
 *
 * - Any Ctrl / Meta / Alt chord is ignored (leaves browser + OS shortcuts).
 * - Inside an input / textarea / select / contentEditable, only `Escape`
 *   passes through (to close the panel / drawer); everything else is typing.
 */
export function resolveKeyAction(event: KeyEventLike): KeyAction | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null;

  const editable = isEditableTarget(event.target);
  if (editable) {
    return event.key === "Escape" ? "closeOverlay" : null;
  }

  switch (event.key) {
    case " ":
    case "Spacebar": // legacy name, harmless to keep for Chrome-only target
      return "playPause";
    case "ArrowLeft":
      return event.shiftKey ? "stepBarBack" : "stepBeatBack";
    case "ArrowRight":
      return event.shiftKey ? "stepBarForward" : "stepBeatForward";
    case "+":
    case "=":
    case "]":
      return "zoomIn";
    case "-":
    case "_":
    case "[":
      return "zoomOut";
    case "f":
    case "F":
      return "fitToWidth";
    case "Escape":
      return "closeOverlay";
    default:
      return null;
  }
}

/** Actions that should `preventDefault()` (they collide with a browser default:
 *  space scrolls, `/` quick-find, arrows scroll the timeline). */
const PREVENT_DEFAULT: ReadonlySet<KeyAction> = new Set<KeyAction>([
  "playPause",
  "stepBeatBack",
  "stepBeatForward",
  "stepBarBack",
  "stepBarForward",
]);

export function shouldPreventDefault(action: KeyAction): boolean {
  return PREVENT_DEFAULT.has(action);
}
