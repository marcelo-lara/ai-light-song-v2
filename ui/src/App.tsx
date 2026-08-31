import { useState } from "react";

type DrawerView = "song" | "timeline" | "inspector" | "review";

interface DrawerEntry {
  id: DrawerView;
  label: string;
  icon: string;
}

const DRAWER_ENTRIES: readonly DrawerEntry[] = [
  { id: "song", label: "Select Song", icon: "ph-file-audio" },
  { id: "timeline", label: "Timeline", icon: "ph-waveform" },
  { id: "inspector", label: "Artifact inspector", icon: "ph-squares-four" },
  { id: "review", label: "Review queue", icon: "ph-flag" },
] as const;

/** The design's five expanded lanes (design-notes §2). Bodies are stubbed until
 *  plan item 3+. */
const STUB_LANES: readonly { id: string; label: string; sub: string; height: number }[] = [
  { id: "waveform", label: "Waveform Anchor", sub: "audio", height: 84 },
  { id: "humanHints", label: "Human Hints", sub: "reference/human", height: 58 },
  { id: "fftBands", label: "FFT Bands", sub: "essentia", height: 84 },
  { id: "rmsLoudness", label: "RMS Loudness", sub: "essentia · 5 stems", height: 112 },
  { id: "loudnessEnvelope", label: "Loudness Envelope", sub: "essentia · 5 stems", height: 112 },
] as const;

const PX_PER_BAR_MIN = 14;
const PX_PER_BAR_MAX = 180;

export function App(): React.JSX.Element {
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [activeView, setActiveView] = useState<DrawerView>("timeline");
  const [pxPerBar, setPxPerBar] = useState(62);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__left">
          <button
            type="button"
            className="tp"
            style={{ fontSize: 18 }}
            aria-label="Toggle menu"
            aria-pressed={drawerOpen}
            onClick={() => setDrawerOpen((open) => !open)}
          >
            <i className="ph ph-list" />
          </button>
          <div className="app-header__divider" />
          <div className="app-header__transport">
            <button type="button" className="tp" aria-label="To start"><i className="ph ph-skip-back" /></button>
            <button type="button" className="tp" aria-label="Rewind"><i className="ph ph-rewind" /></button>
            <button type="button" className="tp" aria-label="Previous beat"><i className="ph ph-caret-left" /></button>
            <button type="button" className="tp tp-main" aria-label="Play"><i className="ph ph-play" /></button>
            <button type="button" className="tp" aria-label="Next beat"><i className="ph ph-caret-right" /></button>
            <button type="button" className="tp" aria-label="Fast forward"><i className="ph ph-fast-forward" /></button>
          </div>
        </div>

        <div className="app-header__center">
          <div>
            <span className="app-header__time">0:00.0</span>
            <span className="app-header__time-sep"> / </span>
            <span className="app-header__total">0:00.0</span>
          </div>
          <div className="app-header__divider" />
          <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)" }}>
            <span className="app-header__barbeat">1.1</span>
            <span className="app-header__barbeat-caption">bar.beat</span>
          </div>
        </div>

        <div className="app-header__right">
          <div className="app-header__song">
            <div className="app-header__song-title">No song selected</div>
            <div className="app-header__song-sub">Score Analysis DAW</div>
          </div>
          <div className="app-header__tags">
            <span className="tag tag-accent" style={{ justifyContent: "center" }}>— BPM</span>
            <span className="tag tag-outline" style={{ justifyContent: "center" }}>— key</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        {drawerOpen && (
          <nav className="app-drawer" aria-label="Primary">
            <div>
              <div className="app-drawer__section-label">Analysis</div>
              <div className="nav">
                {DRAWER_ENTRIES.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    className="dr-item"
                    aria-current={activeView === entry.id ? "page" : undefined}
                    onClick={() => setActiveView(entry.id)}
                  >
                    <i className={`ph ${entry.icon}`} />
                    {entry.label}
                  </button>
                ))}
              </div>
            </div>
          </nav>
        )}

        <div className="app-timeline tl">
          <div className="app-timeline__grid">
            {/* Sticky Segments header row */}
            <div
              className="app-timeline__lane-head app-timeline__header-row"
              style={{ position: "sticky", top: 0, zIndex: 9, height: 26 }}
            >
              <i className="ph ph-flag" style={{ fontSize: 11 }} />
              <span>Segments</span>
            </div>
            <div className="app-timeline__header-row" style={{ position: "sticky", top: 0, zIndex: 7, height: 26 }}>
              <div className="app-timeline__stub">segments — stubbed</div>
            </div>

            {/* Sticky Bars ruler row */}
            <div
              className="app-timeline__lane-head app-timeline__ruler-row"
              style={{ position: "sticky", top: 26, zIndex: 9, height: 30 }}
            >
              <span>Bars</span>
            </div>
            <div className="app-timeline__ruler-row" style={{ position: "sticky", top: 26, zIndex: 7, height: 30 }}>
              <div className="app-timeline__stub">bar / beat ruler — stubbed</div>
            </div>

            {/* Stub lanes */}
            {STUB_LANES.map((lane) => (
              <LaneRow key={lane.id} label={lane.label} sub={lane.sub} height={lane.height} active={activeView === "timeline"} />
            ))}
          </div>
        </div>

        {activeView !== "timeline" && (
          <aside className="app-rightpanel" aria-label={activeView}>
            <div className="card-kicker">{drawerLabel(activeView)}</div>
            <p className="card-body">This surface is built in a later plan item. The shell is chrome-only.</p>
          </aside>
        )}
      </main>

      <footer className="app-footer">
        <div className="app-footer__zoom">
          <button type="button" className="zic" aria-label="Zoom out" onClick={() => setPxPerBar((v) => clampPpb(Math.round(v / 1.3)))}>
            <i className="ph ph-magnifying-glass-minus" />
          </button>
          <input
            type="range"
            min={PX_PER_BAR_MIN}
            max={PX_PER_BAR_MAX}
            value={pxPerBar}
            aria-label="Zoom (px per bar)"
            onChange={(event) => setPxPerBar(clampPpb(Number(event.target.value)))}
          />
          <button type="button" className="zic" aria-label="Zoom in" onClick={() => setPxPerBar((v) => clampPpb(Math.round(v * 1.3)))}>
            <i className="ph ph-magnifying-glass-plus" />
          </button>
          <span className="app-footer__ppb">{pxPerBar} px/bar</span>
        </div>
        <button type="button" className="zbtn">
          <i className="ph ph-arrows-out-line-horizontal" />
          Fit to width
        </button>
      </footer>
    </div>
  );
}

function LaneRow({
  label,
  sub,
  height,
  active,
}: {
  label: string;
  sub: string;
  height: number;
  active: boolean;
}): React.JSX.Element {
  return (
    <>
      <div
        className="app-timeline__lane-head"
        style={{ height, flexDirection: "column", alignItems: "flex-start", justifyContent: "center", gap: 2 }}
      >
        <span style={{ color: "var(--color-neutral-300)", textTransform: "none", letterSpacing: 0, fontSize: 11 }}>
          {label}
        </span>
        <span style={{ color: "var(--color-neutral-600)", textTransform: "none", letterSpacing: 0, fontSize: 9 }}>
          {sub}
        </span>
      </div>
      <div className="app-timeline__lane-body" style={{ height }}>
        <div className="app-timeline__stub">{active ? "lane body — stubbed" : ""}</div>
      </div>
    </>
  );
}

function clampPpb(value: number): number {
  return Math.min(PX_PER_BAR_MAX, Math.max(PX_PER_BAR_MIN, value));
}

function drawerLabel(view: DrawerView): string {
  const entry = DRAWER_ENTRIES.find((candidate) => candidate.id === view);
  return entry ? entry.label : view;
}
