import { describe, expect, it } from "vitest";
import { computeLineDiff } from "../diff";
import {
  buildTimeline, cameraTarget, totalFrames, CODE_VIEW_H, LINE_H, diffSide, chapterTargets,
  CHAR_W, CODE_VIEW_W, GUTTER_W,
} from "../timeline";

const chapters = [
  { id: "c1", audio: { duration_ms: 1000 } },
  { id: "c2", audio: { duration_ms: 2500 } },
] as never[];

describe("buildTimeline", () => {
  it("chapter length is ceil(ms/1000*fps) + 15 and ranges do not overlap", () => {
    const t = buildTimeline(chapters as never, 30);
    expect(t[0]).toEqual({ id: "c1", from: 0, durationInFrames: 45 });
    expect(t[1]).toEqual({ id: "c2", from: 45, durationInFrames: 90 });
    expect(totalFrames(t)).toBe(135);
  });
});

describe("cameraTarget", () => {
  const lines = computeLineDiff("", Array.from({ length: 200 }, (_, i) => `l${i}`).join("\n") + "\n");

  it("scale is 1 for show and clamped <= 2.2 for zoom", () => {
    const focus = { start: 50, end: 54, anchor: "l49" };
    expect(cameraTarget(lines, focus, "show", "new").scale).toBe(1);
    const z = cameraTarget(lines, focus, "zoom", "new").scale;
    expect(z).toBeGreaterThan(1);
    expect(z).toBeLessThanOrEqual(2.2);
  });

  it("zoom scale follows clamp(viewportH / (focusLines * 28 * 1.4), 1, 2.2)", () => {
    const focus = { start: 50, end: 79, anchor: "l49" }; // 30 lines
    const expected = Math.min(2.2, Math.max(1, CODE_VIEW_H / (30 * LINE_H * 1.4)));
    expect(cameraTarget(lines, focus, "zoom", "new").scale).toBeCloseTo(expected);
  });

  it("y is clamped so code never leaves the window", () => {
    const top = cameraTarget(lines, { start: 1, end: 2, anchor: "l0" }, "show", "new");
    expect(top.y).toBe(0);
    const bottom = cameraTarget(lines, { start: 199, end: 200, anchor: "l198" }, "show", "new");
    expect(bottom.y).toBe(CODE_VIEW_H - lines.length * LINE_H);
  });

  it("single-line focus (start === end) clamps zoom scale to 2.2", () => {
    // 1 line: clamp(868 / (1 * 28 * 1.4), 1, 2.2) = 2.2, then snapped down to the
    // nearest scale that shows whole rows: 868 / (15 * 28) = 2.0667.
    const focus = { start: 50, end: 50, anchor: "l49" };
    const s = cameraTarget(lines, focus, "zoom", "new").scale;
    expect(s).toBeLessThanOrEqual(2.2);
    expect(s).toBeCloseTo(CODE_VIEW_H / (15 * LINE_H));
  });

  it("zoom never scales past the width of the widest focused line", () => {
    const long = "x".repeat(120);
    const wide = computeLineDiff(
      "",
      Array.from({ length: 200 }, (_, i) => (i === 51 ? long : `l${i}`)).join("\n") + "\n",
    );
    const focus = { start: 50, end: 54, anchor: "l49" }; // includes the 120-char line
    const { scale } = cameraTarget(wide, focus, "zoom", "new");
    // The gutter scales with the text, so the whole row has to fit the window.
    expect((GUTTER_W + long.length * CHAR_W) * scale).toBeLessThanOrEqual(CODE_VIEW_W);
    // A narrow focus in the same file still gets the full height-driven zoom.
    const narrow = cameraTarget(wide, { start: 60, end: 64, anchor: "l59" }, "zoom", "new");
    expect(narrow.scale).toBeGreaterThan(scale);
  });

  it("scale and y land on whole rows so no line is sliced at an edge", () => {
    const onGrid = (v: number, step: number) => Math.abs(v / step - Math.round(v / step));
    for (const n of [1, 2, 5, 9, 14, 20, 30, 60]) {
      for (const action of ["show", "zoom"] as const) {
        const { y, scale } = cameraTarget(
          lines,
          { start: 50, end: 49 + n, anchor: "l49" },
          action,
          "new",
        );
        const step = LINE_H * scale;
        // Whole rows fill the viewport, and the top edge sits on a row boundary.
        expect(onGrid(CODE_VIEW_H, step)).toBeLessThan(1e-9);
        expect(onGrid(y, step)).toBeLessThan(1e-9);
      }
    }
  });
});

describe("diffSide", () => {
  it("returns 'old' for 'deleted' and 'new' for 'added'/'modified'/'renamed'", () => {
    expect(diffSide("deleted")).toBe("old");
    expect(diffSide("added")).toBe("new");
    expect(diffSide("modified")).toBe("new");
    expect(diffSide("renamed")).toBe("new");
  });
});

describe("chapterTargets", () => {
  it("builds correct targets with highlight reuse and mixed file sides", () => {
    const fileA = Array.from({ length: 60 }, (_, i) => `a${i}`).join("\n") + "\n";
    const fileD = Array.from({ length: 40 }, (_, i) => `d${i}`).join("\n") + "\n";
    const data = {
      files: [
        { path: "A", before: "", after: fileA, status: "added" },
        { path: "D", before: fileD, after: "", status: "deleted" },
      ],
      chapters: [
        { id: "overview", file: null, focus: null, action: "show", audio: { duration_ms: 1000 } },
        { id: "zoomA", file: "A", focus: { start: 20, end: 25, anchor: "a19" }, action: "zoom", audio: { duration_ms: 1000 } },
        { id: "highlightA", file: "A", focus: { start: 20, end: 25, anchor: "a19" }, action: "highlight", audio: { duration_ms: 1000 } },
        { id: "showD", file: "D", focus: { start: 10, end: 15, anchor: "d9" }, action: "show", audio: { duration_ms: 1000 } },
        { id: "closing", file: null, focus: null, action: "show", audio: { duration_ms: 1000 } },
      ],
    } as never;

    const targets = chapterTargets(data);
    expect(targets.length).toBe(5);

    // targets[0] and targets[4] should be null (overview and closing have no file/focus)
    expect(targets[0]).toBeNull();
    expect(targets[4]).toBeNull();

    // targets[2] (highlight) should reuse targets[1] (same file, same focus)
    expect(targets[2]).toBe(targets[1]);

    // targets[3] (showD) should use the old side (deleted file)
    const linesD = computeLineDiff(fileD, "");
    const expectedD = cameraTarget(linesD, { start: 10, end: 15, anchor: "d9" }, "show", "old");
    expect(targets[3]).toEqual(expectedD);
  });
});
