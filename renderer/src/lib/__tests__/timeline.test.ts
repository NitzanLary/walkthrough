import { describe, expect, it } from "vitest";
import { computeLineDiff, focusIndexRange } from "../diff";
import {
  buildTimeline, cameraTarget, totalFrames, CODE_VIEW_H, LINE_H, diffSide, chapterTargets,
  CHAR_W, CODE_VIEW_W, GUTTER_W, CONTEXT_LINES, SHOW_MAX_SCALE, dimFor, maxScaleForWidth,
  LEAD_LINES, ZOOM_MIN_SCALE,
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

  it("show frames the focus but stays below the zoom cap", () => {
    const focus = { start: 50, end: 54, anchor: "l49" };
    const s = cameraTarget(lines, focus, "show", "new").scale;
    expect(s).toBeGreaterThan(1);
    expect(s).toBeLessThanOrEqual(SHOW_MAX_SCALE);
    const z = cameraTarget(lines, focus, "zoom", "new").scale;
    expect(z).toBeGreaterThan(s); // zoom is still the stronger move
    expect(z).toBeLessThanOrEqual(2.2);
  });

  it("show keeps CONTEXT_LINES rows of context around the focus", () => {
    const focus = { start: 50, end: 62, anchor: "l49" }; // 13 lines, like c04
    const { scale } = cameraTarget(lines, focus, "show", "new");
    const visible = CODE_VIEW_H / (LINE_H * scale);
    expect(visible).toBeGreaterThanOrEqual(13 + CONTEXT_LINES - 1);
    expect(visible).toBeLessThan(13 + CONTEXT_LINES + LINE_H);
  });

  it("a focus line too wide for scale 1 does not block framing", () => {
    // 209 chars cannot fit at any scale >= 1, so the width cap steps aside
    // rather than pinning the chapter at scale 1 (real case: examples/small.json).
    const huge = "x".repeat(209);
    const withHuge = computeLineDiff(
      "",
      Array.from({ length: 200 }, (_, i) => (i === 55 ? huge : `l${i}`)).join("\n") + "\n",
    );
    expect(maxScaleForWidth(209)).toBeLessThan(1);
    const { scale } = cameraTarget(withHuge, { start: 50, end: 62, anchor: "l49" }, "show", "new");
    expect(scale).toBeGreaterThan(1);
  });

  it("a focus taller than the frame opens at its own start, not its middle", () => {
    // 40 after-lines is inside the 60-line authoring cap, but 40 rows is 1120px
    // against an 868px viewport: centring would open the chapter 4 rows below
    // focus.start and leave the anchor off-screen.
    const { y, scale } = cameraTarget(lines, { start: 50, end: 89, anchor: "l49" }, "show", "new");
    const [a] = focusIndexRange(lines, { start: 50, end: 89, anchor: "l49" }, "new");
    expect(y).toBeCloseTo((LEAD_LINES * LINE_H - a * LINE_H) * scale);
    // The anchor row sits inside the viewport, LEAD_LINES down from the top.
    const anchorTop = a * LINE_H * scale + y;
    expect(anchorTop).toBeGreaterThanOrEqual(0);
    expect(anchorTop).toBeLessThan(CODE_VIEW_H);
  });

  it("deleted rows inside an after-file focus do not push the anchor out of frame", () => {
    // The real shape from issue #29: an after-file range whose interior holds a
    // deleted hunk, so the rendered region is taller than end - start + 1.
    const src = Array.from({ length: 120 }, (_, i) => `l${i}`);
    const withDel = computeLineDiff(
      // 10 lines removed just inside the focus; the focus is still after-coords.
      [...src.slice(0, 40), ...Array.from({ length: 10 }, (_, i) => `gone${i}`), ...src.slice(40)]
        .join("\n") + "\n",
      src.join("\n") + "\n",
    );
    const focus = { start: 30, end: 65, anchor: "l29" }; // 36 after-lines, 46 rows
    const [a, b] = focusIndexRange(withDel, focus, "new");
    expect(b - a + 1).toBeGreaterThan(focus.end - focus.start + 1); // deletions add rows
    const { y, scale } = cameraTarget(withDel, focus, "scroll", "new");
    const anchorTop = a * LINE_H * scale + y;
    expect(anchorTop).toBeGreaterThanOrEqual(0);
    expect(anchorTop).toBeLessThan(CODE_VIEW_H);
  });

  it("a focus that fits the frame is still centred", () => {
    const focus = { start: 50, end: 59, anchor: "l49" };
    const { y, scale } = cameraTarget(lines, focus, "show", "new");
    const [a, b] = focusIndexRange(lines, focus, "new");
    const centre = (a * LINE_H + ((b - a + 1) * LINE_H) / 2) * scale + y;
    expect(Math.abs(centre - CODE_VIEW_H / 2)).toBeLessThanOrEqual((LINE_H * scale) / 2);
  });

  it("a tall zoom is floored so it never renders as a show", () => {
    // 30 lines drives the height fit below 1 (868 / (30 * 28 * 1.4) = 0.74),
    // which used to clamp to scale 1 — identical to `show`.
    const focus = { start: 50, end: 79, anchor: "l49" };
    const shown = cameraTarget(lines, focus, "show", "new").scale;
    const zoomed = cameraTarget(lines, focus, "zoom", "new").scale;
    expect(shown).toBe(1);
    expect(zoomed).toBeGreaterThan(shown);
    // snapScale rounds down to a whole row count, so the floor lands just under it.
    expect(zoomed).toBeCloseTo(CODE_VIEW_H / (Math.ceil(CODE_VIEW_H / (LINE_H * ZOOM_MIN_SCALE)) * LINE_H));
  });

  it("the zoom floor yields to a width cap that can be met", () => {
    // A 120-char row fits at 1.10 but not at 1.25: clipping the focused code off
    // the right edge is worse than a zoom that reads weakly.
    const long = "x".repeat(120);
    const wide = computeLineDiff(
      "",
      Array.from({ length: 200 }, (_, i) => (i === 60 ? long : `l${i}`)).join("\n") + "\n",
    );
    const cap = maxScaleForWidth(long.length);
    expect(cap).toBeGreaterThan(1);
    expect(cap).toBeLessThan(ZOOM_MIN_SCALE);
    const { scale } = cameraTarget(wide, { start: 50, end: 79, anchor: "l49" }, "zoom", "new");
    expect((GUTTER_W + long.length * CHAR_W) * scale).toBeLessThanOrEqual(CODE_VIEW_W);
  });

  it("dimFor separates the actions", () => {
    expect(dimFor("zoom")).toBeLessThan(dimFor("show"));
    expect(dimFor("show")).toBeLessThan(1);
    expect(dimFor("highlight")).toBe(1);
  });

  it("zoom scale follows clamp(viewportH / (focusLines * 28 * 1.4), ZOOM_MIN_SCALE, 2.2)", () => {
    // 15 lines, where the height fit and not the floor is the binding constraint.
    const focus = { start: 50, end: 64, anchor: "l49" };
    const expected = Math.min(2.2, Math.max(ZOOM_MIN_SCALE, CODE_VIEW_H / (15 * LINE_H * 1.4)));
    expect(cameraTarget(lines, focus, "zoom", "new").scale).toBeCloseTo(expected);
  });

  it("y is clamped so code never leaves the window", () => {
    const top = cameraTarget(lines, { start: 1, end: 2, anchor: "l0" }, "show", "new");
    expect(top.y).toBe(0);
    const bottom = cameraTarget(lines, { start: 199, end: 200, anchor: "l198" }, "show", "new");
    expect(bottom.y).toBeCloseTo(CODE_VIEW_H - lines.length * LINE_H * bottom.scale);
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
