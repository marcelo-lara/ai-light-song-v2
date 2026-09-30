// SongPicker.tsx — the "Select Song" drawer view. Split out of App.tsx (v3.9
// item 7) with no behaviour change.

import type { SongListState } from "./loadStates";

export function SongPicker({
  listState,
  current,
  onPick,
}: {
  listState: SongListState;
  current: string | null;
  onPick: (song: string) => void;
}): React.JSX.Element {
  return (
    <div className="app-rightpanel" style={{ width: "100%", borderLeft: "none" }}>
      <div className="card-kicker">Select Song</div>

      {listState.kind === "loading" && (
        <p className="card-body">Discovering analysed songs…</p>
      )}
      {listState.kind === "error" && (
        <p className="card-body">Discovery failed: {listState.message}</p>
      )}
      {listState.kind === "empty" && (
        <p className="card-body">
          No analysed songs found. Run the analysis pipeline so a song appears in
          both <code>data/analysis/</code> and <code>data/songs/</code>.
        </p>
      )}

      {listState.kind === "ready" && (
        <div className="nav" style={{ marginTop: "var(--space-4)" }}>
          {listState.songs.map((name) => (
            <button
              key={name}
              type="button"
              className="dr-item"
              aria-current={name === current ? "page" : undefined}
              onClick={() => onPick(name)}
            >
              <i className="ph ph-file-audio" />
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
