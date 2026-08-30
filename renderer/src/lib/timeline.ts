import type { Action, Chapter, Focus, Walkthrough } from "./schema";
import { computeLineDiff, focusIndexRange, type LineInfo } from "./diff";
import { wrapLines, type VisualRow } from "./wrap";

export type ChapterTiming = { id: string; from: number; durationInFrames: number };

export function buildTimeline(chapters: Chapter[], fps: number): ChapterTiming[] {
  let from = 0;
  return chapters.map((ch) => {
    const durationInFrames = Math.ceil((ch.audio.duration_ms / 1000) * fps) + 15;
    const t = { id: ch.id, from, durationInFrames };
    from += durationInFrames;
    return t;
  });
}

export function totalFrames(timeline: ChapterTiming[]): number {
  if (timeline.length === 0) return 0;
  const last = timeline[timeline.length - 1];
  return last.from + last.durationInFrames;
}

export const LINE_H = 28;
export const CODE_VIEW_W = 1600;
export const VIEW_LINES = 31;
// A whole number of rows: a viewport that is not a multiple of LINE_H slices the
// row at its bottom edge through the middle of the glyphs. (916px window - 48px tab bar.)
export const CODE_VIEW_H = VIEW_LINES * LINE_H; // 868
// JetBrains Mono advance width at fontSize 18 (0.6em), measured in the browser.
export const CHAR_W = 10.8;
// CodePane row prefix: 3px focus bar + two 56px number columns + 24px gap.
export const GUTTER_W = 139;
// Breathing room so the longest focused line does not kiss the window edge.
export const RIGHT_PAD = 16;
// The widest row the window can hold at scale 1. Every line is wrapped to this,
// which is what keeps the width fit below satisfiable: no rendered row can be so
// wide that no scale >= 1 fits it, so no row is ever clipped at the right edge.
export const WRAP_COLS = Math.floor((CODE_VIEW_W - RIGHT_PAD - GUTTER_W) / CHAR_W);
// Rows of surrounding context a non-zoom action keeps in frame around its focus.
export const CONTEXT_LINES = 8;
// Rows of lead-in kept above a focus too tall to fit: the first focused row sits
// near the top edge rather than flush against it.
export const LEAD_LINES = 2;
// Non-zoom actions frame the focus but stay well short of the zoom cap, so a
// `zoom` chapter still reads as a distinct move.
export const SHOW_MAX_SCALE = 1.6;
export const ZOOM_MAX_SCALE = 2.2;
// A focus tall enough to drive the height fit below 1 would leave `zoom` at scale
// 1 — visually a `show`. Floor it so the move always reads as a zoom; the focus
// then runs past the bottom edge, which the top-anchored framing below handles.
export const ZOOM_MIN_SCALE = 1.25;

/** Opacity of the rows outside the focus range, per camera action. */
export function dimFor(action: Action): number {
  if (action === "zoom") return 0.35;
  if (action === "highlight") return 1; // the focus pulses instead
  return 0.55;
}

/**
 * Largest scale at which a row of `chars` characters still fits across the
 * window. The gutter is inside the scaled content, so it scales along with the
 * text — the whole row width is what has to fit, not just the text.
 */
export function maxScaleForWidth(chars: number): number {
  if (chars <= 0) return Infinity;
  return (CODE_VIEW_W - RIGHT_PAD) / (GUTTER_W + chars * CHAR_W);
}

export type CameraTarget = { y: number; scale: number };

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/**
 * Snap a scale so the viewport holds a whole number of scaled rows. Always rounds
 * the zoom *down* (more rows visible), so the focus range still fits and the 2.2
 * cap still holds.
 */
function snapScale(scale: number): number {
  const visible = Math.ceil(CODE_VIEW_H / (LINE_H * scale));
  return CODE_VIEW_H / (visible * LINE_H);
}

function widestFocusRow(rows: VisualRow[], a: number, b: number): number {
  let max = 0;
  for (let i = a; i <= b; i++) max = Math.max(max, rows[i].text.length);
  return max;
}

export function cameraTarget(
  lines: LineInfo[],
  focus: Focus,
  action: Action,
  side: "old" | "new",
): CameraTarget {
  const { rows, startOf } = wrapLines(lines, WRAP_COLS);
  // Wrapping decouples the focus from its line count: the camera frames rendered
  // rows, of which a wrapped line contributes several.
  const [a, b] = focusIndexRange(lines, focus, side);
  const first = Math.max(0, a);
  const last = Math.min(Math.max(first, b), lines.length - 1);
  const top = startOf[first];
  const bottom = startOf[last + 1] - 1;
  const focusLines = bottom - top + 1;
  const zooming = action === "zoom";
  // Vertical fit. `zoom` fills the frame with the focus plus 40% breathing room;
  // every other action frames the focus but keeps CONTEXT_LINES rows around it,
  // so the file still reads as a file.
  const byHeight = zooming
    ? CODE_VIEW_H / (focusLines * LINE_H * 1.4)
    : CODE_VIEW_H / ((focusLines + CONTEXT_LINES) * LINE_H);
  // Horizontal fit — zooming past this point pushes the focused code off the
  // right edge, since the camera only translates in y. Wrapping caps every row at
  // WRAP_COLS, so this is always satisfiable at scale 1 and never has to be
  // stepped over.
  const widthCap = maxScaleForWidth(widestFocusRow(rows, top, bottom));
  const maxScale = zooming ? ZOOM_MAX_SCALE : SHOW_MAX_SCALE;
  let fit = clamp(Math.min(byHeight, widthCap), 1, maxScale);
  // The floor never overrides a width cap that *can* be met: pushing the focused
  // code off the right edge is worse than a zoom that reads weakly.
  if (zooming) fit = Math.min(Math.max(fit, ZOOM_MIN_SCALE), widthCap);
  const scale = snapScale(fit);

  const focusTop = top * LINE_H;
  const focusH = focusLines * LINE_H;
  // Deletions occupy rows that an after-file range does not count, so a focus can
  // be taller than the frame well inside the 60-line authoring cap. Centring one
  // opens the chapter below its own start line with the anchor off-screen, so pin
  // the first focused row near the top instead and let the rest run past the
  // bottom edge.
  let y = focusH * scale > CODE_VIEW_H
    ? (LEAD_LINES * LINE_H - focusTop) * scale
    : CODE_VIEW_H / 2 - (focusTop + focusH / 2) * scale;
  const contentH = rows.length * LINE_H * scale;
  const minY = Math.min(0, CODE_VIEW_H - contentH);
  // Land the top edge on a row boundary, then clamp: both bounds are already
  // whole multiples of the scaled row, so the clamp cannot reintroduce a slice.
  const step = LINE_H * scale;
  y = clamp(Math.round(y / step) * step, minY, 0);
  return { y, scale };
}

export function diffSide(status: Walkthrough["files"][number]["status"]): "old" | "new" {
  return status === "deleted" ? "old" : "new";
}

export function chapterTargets(data: Walkthrough): (CameraTarget | null)[] {
  const diffCache = new Map<string, LineInfo[]>();
  const linesFor = (path: string): LineInfo[] => {
    if (!diffCache.has(path)) {
      const f = data.files.find((x) => x.path === path)!;
      diffCache.set(path, computeLineDiff(f.before, f.after));
    }
    return diffCache.get(path)!;
  };
  const targets: (CameraTarget | null)[] = [];
  data.chapters.forEach((ch, i) => {
    if (!ch.file || !ch.focus) {
      targets.push(null);
      return;
    }
    const f = data.files.find((x) => x.path === ch.file)!;
    if (ch.action === "highlight") {
      const prev = data.chapters[i - 1];
      targets.push(
        prev && prev.file === ch.file && targets[i - 1]
          ? targets[i - 1]
          : cameraTarget(linesFor(ch.file), ch.focus, "show", diffSide(f.status)),
      );
      return;
    }
    targets.push(cameraTarget(linesFor(ch.file), ch.focus, ch.action, diffSide(f.status)));
  });
  return targets;
}
