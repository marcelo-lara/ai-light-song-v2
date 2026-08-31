// Node model for the collapsible JSON tree viewer. No external lib.
//
// `buildJsonTree` turns an arbitrary parsed-JSON value into a stable tree of
// `JsonNode`s; the React viewer walks that tree and owns only expand/collapse
// UI state. `formatJsonPath` renders a node's path as a copy-pasteable accessor
// string (the "copy path" action).

export type JsonKind =
  | "object"
  | "array"
  | "string"
  | "number"
  | "boolean"
  | "null";

export type JsonPathSegment = string | number;

export interface JsonNode {
  /** Key within the parent; `null` only for the root node. */
  key: JsonPathSegment | null;
  /** Full path from the root (root = `[]`). */
  path: JsonPathSegment[];
  kind: JsonKind;
  /** Container nodes (`object` / `array`) have children; leaves do not. */
  children?: JsonNode[];
  /** Leaf value (primitives only). */
  value?: string | number | boolean | null;
  /** Child count for containers, string length for strings, else 0. */
  size: number;
}

export function jsonKindOf(value: unknown): JsonKind {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  const type = typeof value;
  if (type === "object") return "object";
  if (type === "string") return "string";
  if (type === "number") return "number";
  if (type === "boolean") return "boolean";
  // undefined / function / symbol / bigint are not valid parsed JSON — coerce
  // to a string leaf so the viewer never throws on hand-fed data.
  return "string";
}

export function buildJsonTree(
  value: unknown,
  key: JsonPathSegment | null = null,
  path: JsonPathSegment[] = [],
): JsonNode {
  const kind = jsonKindOf(value);

  if (kind === "object") {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record);
    return {
      key,
      path,
      kind,
      size: keys.length,
      children: keys.map((childKey) =>
        buildJsonTree(record[childKey], childKey, [...path, childKey]),
      ),
    };
  }

  if (kind === "array") {
    const list = value as unknown[];
    return {
      key,
      path,
      kind,
      size: list.length,
      children: list.map((item, index) =>
        buildJsonTree(item, index, [...path, index]),
      ),
    };
  }

  if (kind === "string") {
    const str = typeof value === "string" ? value : String(value);
    return { key, path, kind, value: str, size: str.length };
  }

  return {
    key,
    path,
    kind,
    value: value as number | boolean | null,
    size: 0,
  };
}

export function isContainer(node: JsonNode): boolean {
  return node.kind === "object" || node.kind === "array";
}

/** One-line summary shown on a collapsed container, e.g. `{ } 5 keys`. */
export function containerSummary(node: JsonNode): string {
  if (node.kind === "array") {
    return `[ ] ${node.size} ${node.size === 1 ? "item" : "items"}`;
  }
  return `{ } ${node.size} ${node.size === 1 ? "key" : "keys"}`;
}

const IDENTIFIER = /^[A-Za-z_$][A-Za-z0-9_$]*$/;

/** Render a node path as a JS accessor string: `$.beats[0].time`, `$["form role"]`. */
export function formatJsonPath(path: JsonPathSegment[]): string {
  let out = "$";
  for (const segment of path) {
    if (typeof segment === "number") {
      out += `[${segment}]`;
    } else if (IDENTIFIER.test(segment)) {
      out += `.${segment}`;
    } else {
      out += `[${JSON.stringify(segment)}]`;
    }
  }
  return out;
}

/** Preview string for a leaf value (used inline in the tree). */
export function formatLeaf(node: JsonNode): string {
  if (node.kind === "string") return JSON.stringify(node.value);
  if (node.kind === "null") return "null";
  return String(node.value);
}

/**
 * Paths that should start expanded: the root and everything down to `depth`
 * levels. Used to seed the viewer's expansion set.
 */
export function defaultExpandedPaths(root: JsonNode, depth = 1): Set<string> {
  const expanded = new Set<string>();
  const visit = (node: JsonNode, level: number): void => {
    if (!isContainer(node)) return;
    if (level <= depth) {
      expanded.add(formatJsonPath(node.path));
      for (const child of node.children ?? []) visit(child, level + 1);
    }
  };
  visit(root, 0);
  return expanded;
}
