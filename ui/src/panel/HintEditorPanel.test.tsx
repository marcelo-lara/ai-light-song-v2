// HintEditorPanel — plan v1.5 item 8: the read-only "Captured from" note.

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { HumanHintsFile } from "../data/types";

import { HintEditorPanel } from "./HintEditorPanel";

const base = {
  song: "RegFull - Fixture",
  currentTime: 0,
  seed: null,
  onClose: () => {},
  onSaved: () => {},
  onScrollToTime: () => {},
};

function fileWith(
  capturedFrom?: string,
  type?: "hint" | "review" | "vocal",
): HumanHintsFile {
  return {
    song_name: "RegFull - Fixture",
    human_hints: [
      {
        id: "hint-001",
        title: "Drop - approach",
        start_time: 40,
        end_time: 48,
        summary: "",
        lighting_hint: "",
        ...(capturedFrom ? { captured_from: capturedFrom } : {}),
        ...(type ? { type } : {}),
      },
    ],
  };
}

describe("HintEditorPanel — captured_from note", () => {
  it("renders the read-only line for a captured hint", () => {
    const { getByText } = render(
      <HintEditorPanel
        {...base}
        file={fileWith("allin1 Sections · experiments/allin1")}
        activeReference="hint-001"
      />,
    );
    expect(
      getByText("Captured from allin1 Sections · experiments/allin1"),
    ).toBeTruthy();
  });

  it("shows no line for a hand-authored hint", () => {
    const { queryByText } = render(
      <HintEditorPanel {...base} file={fileWith()} activeReference="hint-001" />,
    );
    expect(queryByText(/^Captured from/)).toBeNull();
  });
});

describe("HintEditorPanel — type dropdown", () => {
  it("defaults to 'review' for a captured hint and 'hint' for a hand-authored one", () => {
    const { getByLabelText, rerender } = render(
      <HintEditorPanel
        {...base}
        file={fileWith("allin1 Sections · experiments/allin1")}
        activeReference="hint-001"
      />,
    );
    expect((getByLabelText("Type") as HTMLSelectElement).value).toBe("review");

    rerender(
      <HintEditorPanel {...base} file={fileWith()} activeReference="hint-001" />,
    );
    expect((getByLabelText("Type") as HTMLSelectElement).value).toBe("hint");
  });

  it("offers exactly the hint/review/vocal options, and shows 'vocal' for an explicitly-typed hint", () => {
    const { getByLabelText } = render(
      <HintEditorPanel
        {...base}
        file={fileWith(undefined, "vocal")}
        activeReference="hint-001"
      />,
    );
    const select = getByLabelText("Type") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      "hint",
      "review",
      "vocal",
    ]);
    expect(select.value).toBe("vocal");
  });
});
