// FitToWidthButton — item 7 (icon-only "fit to width" control).

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FitToWidthButton } from "./FitToWidthButton";

describe("item 7 — fit to width is an icon-only control", () => {
  it("renders no text node, keeps an accessible name, has a single icon", () => {
    const { getByTestId } = render(<FitToWidthButton onClick={() => {}} />);
    const btn = getByTestId("fit-to-width");
    expect(btn.textContent).toBe("");
    expect(btn).toHaveAttribute("aria-label", "Fit to width");
    expect(btn.querySelectorAll("i")).toHaveLength(1);
    expect(btn.querySelector("i")?.className).toContain("ph-");
  });

  it("uses the shared `.zic` icon-button class (no border, hover-swap treatment)", () => {
    // `.zic` is the exact class zoom-in / zoom-out use: `border: none` and a
    // transition-less `background: var(--color-neutral-900)` on :hover.
    const { getByTestId } = render(<FitToWidthButton onClick={() => {}} />);
    const btn = getByTestId("fit-to-width");
    expect(btn.className).toBe("zic");
    expect(btn.className).not.toContain("zbtn");
  });

  it("fires its action on click", () => {
    const onClick = vi.fn();
    const { getByTestId } = render(<FitToWidthButton onClick={onClick} />);
    fireEvent.click(getByTestId("fit-to-width"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
