import { describe, expect, it } from "vitest";

import {
  isEditableTarget,
  resolveKeyAction,
  shouldPreventDefault,
} from "./keymap";

describe("resolveKeyAction", () => {
  it("maps space to play/pause", () => {
    expect(resolveKeyAction({ key: " " })).toBe("playPause");
    expect(resolveKeyAction({ key: "Spacebar" })).toBe("playPause");
  });

  it("maps arrows to beat steps and shift+arrows to bar steps", () => {
    expect(resolveKeyAction({ key: "ArrowLeft" })).toBe("stepBeatBack");
    expect(resolveKeyAction({ key: "ArrowRight" })).toBe("stepBeatForward");
    expect(resolveKeyAction({ key: "ArrowLeft", shiftKey: true })).toBe("stepBarBack");
    expect(resolveKeyAction({ key: "ArrowRight", shiftKey: true })).toBe("stepBarForward");
  });

  it("maps + = ] to zoom in and - _ [ to zoom out (§10 deviation)", () => {
    for (const key of ["+", "=", "]"]) {
      expect(resolveKeyAction({ key })).toBe("zoomIn");
    }
    for (const key of ["-", "_", "["]) {
      expect(resolveKeyAction({ key })).toBe("zoomOut");
    }
  });

  it("maps f / F to fit-to-width and Escape to close", () => {
    expect(resolveKeyAction({ key: "f" })).toBe("fitToWidth");
    expect(resolveKeyAction({ key: "F" })).toBe("fitToWidth");
    expect(resolveKeyAction({ key: "Escape" })).toBe("closeOverlay");
  });

  it("returns null for unmapped keys", () => {
    expect(resolveKeyAction({ key: "a" })).toBeNull();
    expect(resolveKeyAction({ key: "Enter" })).toBeNull();
    expect(resolveKeyAction({ key: "1" })).toBeNull();
  });

  it("ignores any Ctrl / Meta / Alt chord", () => {
    expect(resolveKeyAction({ key: " ", ctrlKey: true })).toBeNull();
    expect(resolveKeyAction({ key: "ArrowLeft", metaKey: true })).toBeNull();
    expect(resolveKeyAction({ key: "f", altKey: true })).toBeNull();
  });

  describe("input-focus guard", () => {
    it("suppresses every shortcut except Escape when focus is in a text control", () => {
      for (const tagName of ["INPUT", "TEXTAREA", "SELECT"]) {
        expect(resolveKeyAction({ key: " ", target: { tagName } })).toBeNull();
        expect(resolveKeyAction({ key: "ArrowLeft", target: { tagName } })).toBeNull();
        expect(resolveKeyAction({ key: "f", target: { tagName } })).toBeNull();
        expect(resolveKeyAction({ key: "Escape", target: { tagName } })).toBe(
          "closeOverlay",
        );
      }
    });

    it("suppresses shortcuts inside contentEditable", () => {
      expect(
        resolveKeyAction({ key: " ", target: { isContentEditable: true } }),
      ).toBeNull();
    });

    it("does not suppress on a non-editable element", () => {
      expect(resolveKeyAction({ key: " ", target: { tagName: "BUTTON" } })).toBe(
        "playPause",
      );
      expect(resolveKeyAction({ key: " ", target: { tagName: "DIV" } })).toBe(
        "playPause",
      );
    });
  });

  it("isEditableTarget tolerates non-object targets", () => {
    expect(isEditableTarget(null)).toBe(false);
    expect(isEditableTarget(undefined)).toBe(false);
    expect(isEditableTarget("INPUT")).toBe(false);
  });
});

describe("shouldPreventDefault", () => {
  it("is true for transport keys that collide with scroll", () => {
    expect(shouldPreventDefault("playPause")).toBe(true);
    expect(shouldPreventDefault("stepBeatForward")).toBe(true);
    expect(shouldPreventDefault("stepBarBack")).toBe(true);
  });

  it("is false for zoom / fit / close", () => {
    expect(shouldPreventDefault("zoomIn")).toBe(false);
    expect(shouldPreventDefault("fitToWidth")).toBe(false);
    expect(shouldPreventDefault("closeOverlay")).toBe(false);
  });
});
