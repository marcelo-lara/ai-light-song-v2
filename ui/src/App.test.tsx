import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";

afterEach(() => globalThis.localStorage?.clear());

/** Item 4: the left panel is collapsed by default — open it for drawer checks. */
function openDrawer(): void {
  fireEvent.click(screen.getByRole("button", { name: "Toggle menu" }));
}

describe("App shell", () => {
  it("renders the three fixed bands and the timeline surface", () => {
    const { container } = render(<App />);
    expect(container.querySelector(".app-header")).toBeInTheDocument();
    expect(container.querySelector(".app-main")).toBeInTheDocument();
    expect(container.querySelector(".app-footer")).toBeInTheDocument();
    expect(container.querySelector(".app-timeline")).toBeInTheDocument();
  });

  it("left panel is collapsed by default", () => {
    render(<App />);
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
  });

  it("has exactly four drawer entries", () => {
    render(<App />);
    openDrawer();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const entries = nav.querySelectorAll(".dr-item");
    expect(entries).toHaveLength(4);
    expect(Array.from(entries, (el) => el.textContent?.trim())).toEqual([
      "Select Song",
      "Timeline",
      "Artifact inspector",
      "Review queue",
    ]);
  });

  it("marks Timeline as the active drawer entry by default", () => {
    render(<App />);
    openDrawer();
    expect(screen.getByRole("button", { name: "Timeline" })).toHaveAttribute("aria-current", "page");
  });

  it("shows the zoom control, its px/bar label and the lane-list toggle", () => {
    render(<App />);
    expect(screen.getByLabelText("Zoom (px per bar)")).toBeInTheDocument();
    expect(screen.getByText("62 px/bar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lanes" })).toBeInTheDocument();
  });

  it("prompts for a song when none is selected", () => {
    render(<App />);
    expect(screen.getByText(/open .Select Song/i)).toBeInTheDocument();
  });

  // item 3: no lane-events panel until a lane opener is clicked (App renders
  // without a song in jsdom, so this just guards the default render path).
  it("renders no lane-events panel by default", () => {
    const { container } = render(<App />);
    expect(
      container.querySelector('[data-testid="lane-events-panel"]'),
    ).toBeNull();
  });
});
