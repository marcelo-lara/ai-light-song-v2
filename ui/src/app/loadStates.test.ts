import { describe, expect, it } from "vitest";

import { selectSongListState, selectSongLoadState } from "./loadStates";

describe("selectSongListState", () => {
  it("is loading before discovery has returned", () => {
    expect(
      selectSongListState({ loaded: false, error: null, songs: [] }),
    ).toEqual({ kind: "loading" });
  });

  it("is error when discovery failed, even with stale songs", () => {
    expect(
      selectSongListState({ loaded: true, error: "boom", songs: ["a"] }),
    ).toEqual({ kind: "error", message: "boom" });
  });

  it("is empty when discovery returned no songs", () => {
    expect(
      selectSongListState({ loaded: true, error: null, songs: [] }),
    ).toEqual({ kind: "empty" });
  });

  it("is ready with a copied song list", () => {
    const songs = ["b", "a"];
    const state = selectSongListState({ loaded: true, error: null, songs });
    expect(state).toEqual({ kind: "ready", songs: ["b", "a"] });
    if (state.kind === "ready") expect(state.songs).not.toBe(songs);
  });
});

describe("selectSongLoadState", () => {
  const base = {
    infoStatus: "ready" as const,
    hasBeats: true,
    laneArtifactStatus: {},
  };

  it("is loading while info.json is in flight", () => {
    expect(selectSongLoadState({ ...base, infoStatus: "loading" })).toEqual({
      kind: "loading",
    });
    expect(selectSongLoadState({ ...base, infoStatus: "idle" })).toEqual({
      kind: "loading",
    });
  });

  it("is fatal when info.json errors", () => {
    expect(
      selectSongLoadState({
        ...base,
        infoStatus: "error",
        infoError: "404",
      }),
    ).toEqual({ kind: "fatal", message: "404" });
  });

  it("is fatal when there is no beat grid", () => {
    const state = selectSongLoadState({ ...base, hasBeats: false });
    expect(state.kind).toBe("fatal");
  });

  it("is degraded and lists the errored lane artifacts, sorted", () => {
    expect(
      selectSongLoadState({
        ...base,
        laneArtifactStatus: {
          "RMS / Loudness": "error",
          FFT: "ready",
          "Human Hints": "error",
        },
      }),
    ).toEqual({ kind: "degraded", missing: ["Human Hints", "RMS / Loudness"] });
  });

  it("is ready when info + beats are present and every lane artifact loaded", () => {
    expect(
      selectSongLoadState({
        ...base,
        laneArtifactStatus: { FFT: "ready", Chords: "loading" },
      }),
    ).toEqual({ kind: "ready" });
  });
});
