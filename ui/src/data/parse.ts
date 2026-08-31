// Small structural-assertion toolkit shared by the artifact parsers.
//
// Every parser is a pure `(raw: unknown) => T` that throws `ShapeError` when the
// input does not match the v1.1 contract. The loaders catch that and turn it
// into a typed `{ ok: false, error: { kind: "shape", ... } }` result.

export class ShapeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ShapeError";
  }
}

export function asObject(value: unknown, ctx: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ShapeError(`${ctx}: expected an object`);
  }
  return value as Record<string, unknown>;
}

export function asArray(value: unknown, ctx: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new ShapeError(`${ctx}: expected an array`);
  }
  return value;
}

export function asNumber(value: unknown, ctx: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ShapeError(`${ctx}: expected a finite number`);
  }
  return value;
}

export function asString(value: unknown, ctx: string): string {
  if (typeof value !== "string") {
    throw new ShapeError(`${ctx}: expected a string`);
  }
  return value;
}

export function asBoolean(value: unknown, ctx: string): boolean {
  if (typeof value !== "boolean") {
    throw new ShapeError(`${ctx}: expected a boolean`);
  }
  return value;
}

// -- nullable / optional coercions -----------------------------------------
// A missing (`undefined`) or explicit `null` field collapses to `null`; a
// present value of the wrong type still throws.

export function numberOrNull(value: unknown, ctx: string): number | null {
  if (value === undefined || value === null) return null;
  return asNumber(value, ctx);
}

export function stringOrNull(value: unknown, ctx: string): string | null {
  if (value === undefined || value === null) return null;
  return asString(value, ctx);
}

export function booleanOrNull(value: unknown, ctx: string): boolean | null {
  if (value === undefined || value === null) return null;
  return asBoolean(value, ctx);
}

export function objectOrNull(
  value: unknown,
  ctx: string,
): Record<string, unknown> | null {
  if (value === undefined || value === null) return null;
  return asObject(value, ctx);
}

/** default a missing number to `fallback`; a present non-number still throws */
export function numberOr(value: unknown, fallback: number, ctx: string): number {
  if (value === undefined || value === null) return fallback;
  return asNumber(value, ctx);
}

export function stringOr(value: unknown, fallback: string, ctx: string): string {
  if (value === undefined || value === null) return fallback;
  return asString(value, ctx);
}

export function booleanOr(
  value: unknown,
  fallback: boolean,
  ctx: string,
): boolean {
  if (value === undefined || value === null) return fallback;
  return asBoolean(value, ctx);
}

export function numberArray(value: unknown, ctx: string): number[] {
  return asArray(value, ctx).map((entry, i) => asNumber(entry, `${ctx}[${i}]`));
}

export function stringArray(value: unknown, ctx: string): string[] {
  return asArray(value, ctx).map((entry, i) => asString(entry, `${ctx}[${i}]`));
}
