import { describe, expect, it } from "vitest";
import { computeLineDiff, focusIndexRange } from "../diff";

describe("computeLineDiff", () => {
  it("interleaves deleted lines with old/new numbering", () => {
    const before = "a\nb\nc\n";
    const after = "a\nB\nc\n";
    const lines = computeLineDiff(before, after);
    expect(lines).toEqual([
      { kind: "ctx", oldNo: 1, newNo: 1, text: "a" },
      { kind: "del", oldNo: 2, newNo: null, text: "b" },
      { kind: "add", oldNo: null, newNo: 2, text: "B" },
      { kind: "ctx", oldNo: 3, newNo: 3, text: "c" },
    ]);
  });

  it("handles pure addition (empty before)", () => {
    const lines = computeLineDiff("", "x\ny\n");
    expect(lines.every((l) => l.kind === "add")).toBe(true);
    expect(lines.map((l) => l.newNo)).toEqual([1, 2]);
  });

  it("handles pure deletion (empty after)", () => {
    const lines = computeLineDiff("x\ny\n", "");
    expect(lines.every((l) => l.kind === "del")).toBe(true);
    expect(lines.map((l) => l.oldNo)).toEqual([1, 2]);
  });
});

describe("focusIndexRange", () => {
  it("maps after-side focus line numbers to array indices", () => {
    const lines = computeLineDiff("a\nb\nc\n", "a\nB\nc\n");
    expect(focusIndexRange(lines, { start: 2, end: 3, anchor: "B" }, "new"))
      .toEqual([2, 3]);
  });

  it("maps before-side focus for deleted files", () => {
    const lines = computeLineDiff("x\ny\n", "");
    expect(focusIndexRange(lines, { start: 1, end: 2, anchor: "x" }, "old"))
      .toEqual([0, 1]);
  });
});
