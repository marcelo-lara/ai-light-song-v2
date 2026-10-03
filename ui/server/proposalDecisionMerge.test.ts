// Pins the v3.9 item 6 cause (missing approved hints on *Tutta L'Italia*)
// and the fix's pure pieces. The mkdir/write path itself is exercised by
// `PUT /api/proposal-decision/<song>` in vite.config.ts (not importable
// here — see runRequestGuard.ts's header for why).

import { describe, expect, it } from "vitest";

import * as merge from "./proposalDecisionMerge";

import {
  applyVerdictOperator,
  buildApprovedHintEntry,
  hintAlreadyCaptured,
  nextHumanHintId,
  proposalCapturedFromMarker,
  withSongLock,
  type MergeHint,
} from "./proposalDecisionMerge";

function hint(id: string, capturedFrom?: string): MergeHint {
  return {
    id,
    title: "t",
    start_time: 0,
    end_time: 1,
    summary: "",
    lighting_hint: "",
    ...(capturedFrom ? { captured_from: capturedFrom } : {}),
  };
}

describe("withSongLock — the actual race", () => {
  it("without serialization, concurrent read-modify-write loses updates (the bug)", async () => {
    let store: string[] = [];
    const appendUnlocked = async (value: string) => {
      const current = [...store]; // "load the current file"
      await new Promise((resolve) => setTimeout(resolve, 0)); // the async fs read/write gap
      current.push(value); // "append in memory"
      store = current; // "write the whole file back"
    };
    await Promise.all(["a", "b", "c"].map(appendUnlocked));
    // At least one of the three concurrent appends is clobbered by another's
    // stale write — exactly what happened to six of Tutta L'Italia's
    // nineteen approved hints.
    expect(store.length).toBeLessThan(3);
  });

  it("with withSongLock, the same interleaving keeps every update", async () => {
    let store: string[] = [];
    const appendLocked = (value: string) =>
      withSongLock("song", async () => {
        const current = [...store];
        await new Promise((resolve) => setTimeout(resolve, 0));
        current.push(value);
        store = current;
      });
    await Promise.all(["a", "b", "c"].map(appendLocked));
    expect(store.sort()).toEqual(["a", "b", "c"]);
  });

  it("serializes independently per song", async () => {
    const order: string[] = [];
    await Promise.all([
      withSongLock("song-x", async () => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        order.push("x");
      }),
      withSongLock("song-y", async () => {
        order.push("y");
      }),
    ]);
    // "y" (a different song) is never blocked behind "x"'s slower lock.
    expect(order).toEqual(["y", "x"]);
  });

  it("a rejection in one operation does not deadlock the next", async () => {
    await expect(
      withSongLock("song-z", async () => {
        throw new Error("boom");
      }),
    ).rejects.toThrow("boom");
    await expect(withSongLock("song-z", async () => "ok")).resolves.toBe("ok");
  });
});

describe("nextHumanHintId", () => {
  it("is one past the highest existing human-hint-<N>, not existingHints.length + 1", () => {
    // Tutta L'Italia's actual surviving shape: human-hint-6..18 (13 entries)
    // plus 5 unrelated hand-authored ids. length + 1 would be 19 here too by
    // coincidence — use a gappier fixture to prove it's really id-derived.
    const existing = [hint("hint-001"), hint("human-hint-6"), hint("human-hint-18")];
    expect(nextHumanHintId(existing)).toBe("human-hint-19");
  });

  it("starts from human-hint-1 when there are no captured hints yet", () => {
    expect(nextHumanHintId([hint("hint-001"), hint("hint-002")])).toBe("human-hint-1");
  });
});

describe("hintAlreadyCaptured", () => {
  it("finds a hint already captured from a given proposal id", () => {
    const existing = [hint("human-hint-1", proposalCapturedFromMarker("prop-abc"))];
    expect(hintAlreadyCaptured(existing, "prop-abc")).toBe(true);
    expect(hintAlreadyCaptured(existing, "prop-other")).toBe(false);
  });
});

describe("buildApprovedHintEntry", () => {
  it("uses the proposal's own times when no correction was made", () => {
    const entry = buildApprovedHintEntry(
      { id: "prop-1", hint: { start: 10, end: 12, title: "Drop", summary: "s" } },
      [],
      null,
    );
    expect(entry).toMatchObject({
      id: "human-hint-1",
      title: "Drop",
      start_time: 10,
      end_time: 12,
      summary: "s",
      captured_from: "MCP proposal prop-1",
      type: "review",
    });
  });

  it("prefers the operator's corrected times over the proposal's", () => {
    const entry = buildApprovedHintEntry(
      { id: "prop-2", hint: { start: 10, end: 12, title: "Drop" } },
      [],
      { start: 9.5, end: 13.25 },
    );
    expect(entry.start_time).toBe(9.5);
    expect(entry.end_time).toBe(13.25);
  });

  it("throws when the proposal has no hint payload", () => {
    expect(() => buildApprovedHintEntry({ id: "prop-3" }, [], null)).toThrow();
  });
});

describe("section-field proposals are gone", () => {
  it("exposes no section-field merge", () => {
    expect(merge).not.toHaveProperty("applyApprovedSectionField");
  });
});

describe("applyVerdictOperator (v3.11 item 24)", () => {
  const doc = () => ({
    schema_version: "3.1",
    verdicts: { fields: { drops: { verdict: "unresolved", evidence: {} } } },
    second_pass: {
      fields: {
        drops: {
          verdict: null, wrong: null, evidence: null, first_pass_verdict: null, operator: null,
        },
      },
    },
  });
  const answer = { answer: "confirmed" as const, reason: null, check_id: "vc1" };

  it("sets only operator and keeps the rest of the entry and the file", () => {
    const d = doc();
    (d.second_pass.fields.drops as Record<string, unknown>).verdict = "refuted";
    const { doc: out, changed } = applyVerdictOperator(d, "drops", answer);
    expect(changed).toBe(true);
    const entry = (out.second_pass as { fields: Record<string, Record<string, unknown>> }).fields.drops!;
    expect(entry.verdict).toBe("refuted");
    expect(entry.operator).toEqual(answer);
    expect(out.verdicts).toEqual(d.verdicts);
  });

  it("creates the second_pass block and an operator-only entry with null siblings", () => {
    const { doc: out } = applyVerdictOperator(
      { verdicts: { fields: { bpm: { verdict: "unresolved" } } } },
      "bpm",
      { answer: "rejected", reason: "no", check_id: "vc2" },
    );
    expect((out.second_pass as { fields: unknown }).fields).toEqual({
      bpm: {
        verdict: null, wrong: null, evidence: null, first_pass_verdict: null,
        operator: { answer: "rejected", reason: "no", check_id: "vc2" },
      },
    });
  });

  it("a retry of the same answer is a no-op", () => {
    const once = applyVerdictOperator(doc(), "drops", answer).doc;
    expect(applyVerdictOperator(once, "drops", answer).changed).toBe(false);
  });

  it("refuses a different answer once one is stored, an unknown field, and a field with no verdict row", () => {
    const once = applyVerdictOperator(doc(), "drops", answer).doc;
    expect(() => applyVerdictOperator(once, "drops", { ...answer, check_id: "vc9" })).toThrow(/already answered/);
    expect(() => applyVerdictOperator(doc(), "tempo", answer)).toThrow(/not one of/);
    expect(() => applyVerdictOperator(doc(), "vocals", answer)).toThrow(/no first-pass verdict/);
  });
});
