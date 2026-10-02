// Absence tests for v3.10 item 9 — the debugger no longer reads, shows or
// edits anything the analyzer cut in item 8. Every pattern below names a
// removed file, field or lane; none may appear in non-test `ui/` source.

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { LANE_DEFS } from "./timeline/laneState";
import { TIMELINE_KEYS } from "./timeline/laneConfig";
import { artifactPaths } from "./data/paths";

const UI_ROOT = path.resolve(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx|css)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

const FILES = [
  ...sourceFiles(path.join(UI_ROOT, "src")),
  ...sourceFiles(path.join(UI_ROOT, "server")),
  path.join(UI_ROOT, "vite.config.ts"),
];

const REMOVED = [
  "layer_c_energy",
  "layer_a_harmonic",
  "genre",
  "energy_source",
  "tension_source",
  "rhythm_source",
  "seed_unreviewed",
  "section_function",
  "section_clues",
  "segments.seed",
  "hpcp",
  "propose_section_field",
  "section_field",
  "review_warning",
  "contested",
  "block_energy",
  "block-energy",
  "blockEnergy",
  "BlockEnergy",
  "segmentSeeds",
  "humanSectionsSeed",
  "harmonicLayer",
  "rhythmDrumIoi",
  "rhythmStemAutocorr",
  "rhythmVocalOnsets",
  "energyLevel",
  "tensionShape",
  "impact_alignment",
];

// Verbatim vocabulary text mirrored from docs/segments-vocabulary.md.
const VOCABULARY_FILE = path.join("src", "data", "segmentFunctions.ts");

describe("removed surfaces", () => {
  it("no non-test ui source names a removed file, field, lane or endpoint", () => {
    const hits: string[] = [];
    for (const file of FILES) {
      const rel = path.relative(UI_ROOT, file);
      if (rel === VOCABULARY_FILE) continue;
      const lines = readFileSync(file, "utf-8").split("\n");
      lines.forEach((line, i) => {
        for (const name of REMOVED) {
          if (line.includes(name)) hits.push(`${rel}:${i + 1} ${name}`);
        }
      });
    }
    expect(hits).toEqual([]);
  });

  it("the word tension survives only as the gesture phase of song_event_timeline", () => {
    const stray: string[] = [];
    for (const file of FILES) {
      readFileSync(file, "utf-8")
        .split("\n")
        .forEach((line, i) => {
          if (
            /\btension\b/i.test(line) &&
            !line.includes("approach/build/tension/impact/release") &&
            !line.includes('| "tension"')
          ) {
            stray.push(`${path.relative(UI_ROOT, file)}:${i + 1}`);
          }
        });
    }
    expect(stray).toEqual([]);
  });

  it("the segment editor and rating code write no energy/rhythm control", () => {
    const hits: string[] = [];
    for (const file of FILES) {
      const rel = path.relative(UI_ROOT, file);
      if (rel === VOCABULARY_FILE) continue;
      readFileSync(file, "utf-8")
        .split("\n")
        .forEach((line, i) => {
          if (/\b(energy|rhythm)\b|seg-rating|SegmentedRating|SEGMENT_RHYTHM/i.test(line)) {
            hits.push(`${rel}:${i + 1}`);
          }
        });
    }
    expect(hits).toEqual([]);
  });
});

describe("lane registry", () => {
  it("has no lane titled or keyed with energy, tension, rhythm, key or seeds", () => {
    for (const lane of LANE_DEFS) {
      expect(`${lane.id} ${lane.label}`).not.toMatch(/energy|tension|rhythm|\bkey\b|seed/i);
    }
  });

  it("loads none of the removed artifacts", () => {
    for (const gone of [
      "harmonicLayer",
      "energyLayer",
      "blockEnergy",
      "humanSectionsSeed",
      "rhythmDrumIoi",
      "energyLevel",
      "tensionShape",
    ]) {
      expect(Object.keys(artifactPaths)).not.toContain(gone);
      expect(TIMELINE_KEYS as readonly string[]).not.toContain(gone);
    }
  });
});
