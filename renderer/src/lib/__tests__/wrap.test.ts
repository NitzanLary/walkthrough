import { describe, expect, it } from "vitest";
import { computeLineDiff } from "../diff";
import { CONT_INDENT, wrapLines, wrapText } from "../wrap";

describe("wrapText", () => {
  it("leaves a line that fits as a single row", () => {
    expect(wrapText("short", 10)).toEqual(["short"]);
    expect(wrapText("exactly-10", 10)).toEqual(["exactly-10"]);
    expect(wrapText("", 10)).toEqual([""]);
  });

  it("continuation rows are narrower by the indent they carry", () => {
    const rows = wrapText("x".repeat(30), 10);
    expect(rows[0]).toHaveLength(10);
    for (const r of rows.slice(1, -1)) expect(r).toHaveLength(10 - CONT_INDENT);
  });

  it("loses no characters — the whole line is still reachable", () => {
    // The bug in #1 was content past the right edge simply vanishing.
    for (const n of [1, 9, 10, 11, 40, 209, 276]) {
      const text = Array.from({ length: n }, (_, i) => String(i % 10)).join("");
      expect(wrapText(text, 10).join("")).toBe(text);
    }
  });
});

describe("wrapLines", () => {
  const lines = computeLineDiff("", ["a", "y".repeat(25), "c"].join("\n") + "\n");

  it("maps each source line to its first row, ending with the total", () => {
    const { rows, startOf } = wrapLines(lines, 10);
    // "a" -> 1 row, the 25-char line -> 1 + ceil(15/8) = 3 rows, "c" -> 1 row.
    expect(startOf).toEqual([0, 1, 4, 5]);
    expect(rows).toHaveLength(5);
    expect(rows.map((r) => r.src)).toEqual([0, 1, 1, 1, 2]);
    expect(rows.map((r) => r.cont)).toEqual([false, false, true, true, false]);
  });

  it("each row knows its offset into the source line, for token slicing", () => {
    const { rows } = wrapLines(lines, 10);
    for (const row of rows) {
      expect(lines[row.src].text.slice(row.start, row.start + row.text.length))
        .toBe(row.text);
    }
  });
});
