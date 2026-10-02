import { describe, expect, it } from "vitest";

import { buildHumanSectionsPayload, saveHumanSections } from "./saveHumanSections";
import { parseHumanSegmentsFile } from "./parsers";
import { SEGMENT_FUNCTION_NAMES } from "./segmentFunctions";
import { SEGMENT_FUNCTION_NAMES as SERVER_NAMES } from "../../server/humanSections";

describe("Drop Break label", () => {
  it("is offered right after Extended Drop, in the same order as the server list", () => {
    expect(SEGMENT_FUNCTION_NAMES[SEGMENT_FUNCTION_NAMES.indexOf("Extended Drop") + 1]).toBe("Drop Break");
    expect(SEGMENT_FUNCTION_NAMES).toEqual([...SERVER_NAMES]);
  });

  it("is accepted and saved by buildHumanSectionsPayload", () => {
    const out = buildHumanSectionsPayload([
      { id: "a", start: "0", end: "8", label: "Drop Break", description: "" } as never,
    ]);
    expect(out[0]!.label).toBe("Drop Break");
  });
});

describe("saving a section", () => {
  it("writes start/end/label/description and nothing else for a fresh row", () => {
    const out = buildHumanSectionsPayload([
      { id: "a", start: "1", end: "9", label: "Intro", description: " warm " },
    ]);
    expect(out).toEqual([{ start: 1, end: 9, label: "Intro", description: "warm" }]);
  });

  it("round-trips keys it does not own exactly as read from disk", async () => {
    const onDisk = [
      { start: 0, end: 8, label: "Intro", energy: 2, tension: 1, rhythm: { drums: "quarter" } },
      { start: 8, end: 16, label: "Drop" , energy: 5 },
    ];
    const drafts = parseHumanSegmentsFile(onDisk).map((s, i) => ({
      id: `segment-${i}`,
      label: s.label ?? "",
      start: s.start,
      end: s.end + (i === 0 ? 1 : 0), // the operator edits one end time
      ...(s.preserved ? { preserved: s.preserved } : {}),
    }));
    const payload = buildHumanSectionsPayload(drafts);
    expect(payload[0]).toEqual({ ...onDisk[0], end: 9 });
    expect(payload[1]).toEqual(onDisk[1]);
    // the server's echo is parsed back with the same keys intact
    const fetchImpl = (async () => new Response(JSON.stringify(payload))) as unknown as typeof fetch;
    const written = await saveHumanSections("s", payload, fetchImpl);
    expect(buildHumanSectionsPayload(written.map((s) => ({
      id: "x", label: s.label ?? "", start: s.start, end: s.end, ...(s.preserved ? { preserved: s.preserved } : {}),
    })))).toEqual(payload);
  });
});
