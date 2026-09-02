import { describe, expect, it } from "vitest";

import {
  buildJsonTree,
  containerSummary,
  defaultExpandedPaths,
  formatJsonPath,
  formatLeaf,
  jsonKindOf,
} from "./jsonTree";

describe("jsonKindOf", () => {
  it("distinguishes null, array and object from primitives", () => {
    expect(jsonKindOf(null)).toBe("null");
    expect(jsonKindOf([])).toBe("array");
    expect(jsonKindOf({})).toBe("object");
    expect(jsonKindOf("x")).toBe("string");
    expect(jsonKindOf(3)).toBe("number");
    expect(jsonKindOf(true)).toBe("boolean");
  });
});

describe("buildJsonTree", () => {
  const tree = buildJsonTree({
    bpm: 120,
    beats: [{ time: 0.5 }, { time: 1.0 }],
    label: "verse",
    nested: null,
  });

  it("models the root object with typed children and sizes", () => {
    expect(tree.kind).toBe("object");
    expect(tree.key).toBeNull();
    expect(tree.size).toBe(4);
    expect(tree.children?.map((c) => c.key)).toEqual([
      "bpm",
      "beats",
      "label",
      "nested",
    ]);
  });

  it("recurses into arrays with numeric keys and index paths", () => {
    const beats = tree.children?.find((c) => c.key === "beats");
    expect(beats?.kind).toBe("array");
    expect(beats?.size).toBe(2);
    const first = beats?.children?.[0];
    expect(first?.kind).toBe("object");
    expect(first?.children?.[0]?.path).toEqual(["beats", 0, "time"]);
    expect(first?.children?.[0]?.value).toBe(0.5);
  });

  it("keeps primitive leaves with their value and kind", () => {
    const label = tree.children?.find((c) => c.key === "label");
    expect(label?.kind).toBe("string");
    expect(label?.value).toBe("verse");
    const nested = tree.children?.find((c) => c.key === "nested");
    expect(nested?.kind).toBe("null");
  });
});

describe("formatJsonPath", () => {
  it("renders identifier keys, quoted keys and indices", () => {
    expect(formatJsonPath([])).toBe("$");
    expect(formatJsonPath(["beats", 0, "time"])).toBe("$.beats[0].time");
    expect(formatJsonPath(["form role"])).toBe('$["form role"]');
    expect(formatJsonPath(["a", "1b"])).toBe('$.a["1b"]');
  });
});

describe("formatLeaf", () => {
  it("quotes strings and stringifies the rest", () => {
    expect(formatLeaf(buildJsonTree("hi"))).toBe('"hi"');
    expect(formatLeaf(buildJsonTree(42))).toBe("42");
    expect(formatLeaf(buildJsonTree(null))).toBe("null");
    expect(formatLeaf(buildJsonTree(false))).toBe("false");
  });
});

describe("containerSummary", () => {
  it("singular / plural for keys and items", () => {
    expect(containerSummary(buildJsonTree({ a: 1 }))).toBe("{ } 1 key");
    expect(containerSummary(buildJsonTree({ a: 1, b: 2 }))).toBe("{ } 2 keys");
    expect(containerSummary(buildJsonTree([1]))).toBe("[ ] 1 item");
    expect(containerSummary(buildJsonTree([1, 2]))).toBe("[ ] 2 items");
  });
});

describe("defaultExpandedPaths", () => {
  it("expands the root and one level of containers by default", () => {
    const tree = buildJsonTree({ a: { b: { c: 1 } }, list: [1, 2] });
    const expanded = defaultExpandedPaths(tree, 1);
    expect(expanded.has("$")).toBe(true);
    expect(expanded.has("$.a")).toBe(true);
    expect(expanded.has("$.list")).toBe(true);
    expect(expanded.has("$.a.b")).toBe(false);
  });
});
