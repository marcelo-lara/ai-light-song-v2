// AppDrawer.tsx — the left-panel navigation. Split out of App.tsx (v3.9 item
// 7) with no behaviour change.

import { DRAWER_ENTRIES, type DrawerView } from "./useDrawer";

export function AppDrawer({
  drawerOpen,
  activeView,
  onSelectView,
  drawerRef,
}: {
  drawerOpen: boolean;
  activeView: DrawerView;
  onSelectView: (view: DrawerView) => void;
  drawerRef: React.RefObject<HTMLElement>;
}): React.JSX.Element {
  return (
    <nav
      className="app-drawer"
      aria-label="Primary"
      data-testid="left-panel"
      data-open={drawerOpen ? "true" : "false"}
      ref={drawerRef}
    >
      <div>
        <div className="app-drawer__section-label">Analysis</div>
        <div className="nav">
          {DRAWER_ENTRIES.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className="dr-item"
              aria-current={activeView === entry.id ? "page" : undefined}
              onClick={() => onSelectView(entry.id)}
            >
              <i className={`ph ${entry.icon}`} />
              {entry.label}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
