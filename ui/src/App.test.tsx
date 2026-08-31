import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App shell", () => {
  it("renders the three fixed bands and the timeline surface", () => {
    const { container } = render(<App />);
    expect(container.querySelector(".app-header")).toBeInTheDocument();
    expect(container.querySelector(".app-main")).toBeInTheDocument();
    expect(container.querySelector(".app-footer")).toBeInTheDocument();
    expect(container.querySelector(".app-timeline")).toBeInTheDocument();
  });

  it("has exactly four drawer entries", () => {
    render(<App />);
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
    expect(screen.getByRole("button", { name: "Timeline" })).toHaveAttribute("aria-current", "page");
  });

  it("renders the design's five expanded lanes as stubs", () => {
    render(<App />);
    for (const label of ["Waveform Anchor", "Human Hints", "FFT Bands", "RMS Loudness", "Loudness Envelope"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});
