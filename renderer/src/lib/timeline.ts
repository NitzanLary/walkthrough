import type { Action, Chapter, Focus, Walkthrough } from "./schema";
import { computeLineDiff, focusIndexRange, type LineInfo } from "./diff";

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
// Rows of surrounding context a non-zoom action keeps in frame around its focus.
export const CONTEXT_LINES = 8;
// Non-zoom actions frame the focus but stay well short of the zoom cap, so a
// `zoom` chapter still reads as a distinct move.
export const SHOW_MAX_SCALE = 1.6;
export const ZOOM_MAX_SCALE = 2.2;

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

function widestFocusLine(lines: LineInfo[], a: number, b: number): number {
  let max = 0;
  for (let i = Math.max(0, a); i <= Math.min(lines.length - 1, b); i++) {
    max = Math.max(max, lines[i].text.length);
  }
  return max;
}

export function cameraTarget(
  lines: LineInfo[],
  focus: Focus,
  action: Action,
  side: "old" | "new",
): CameraTarget {
  const [a, b] = focusIndexRange(lines, focus, side);
  const focusLines = b - a + 1;
  const zooming = action === "zoom";
  // Vertical fit. `zoom` fills the frame with the focus plus 40% breathing room;
  // every other action frames the focus but keeps CONTEXT_LINES rows around it,
  // so the file still reads as a file.
  const byHeight = zooming
    ? CODE_VIEW_H / (focusLines * LINE_H * 1.4)
    : CODE_VIEW_H / ((focusLines + CONTEXT_LINES) * LINE_H);
  // Horizontal fit — zooming past this point pushes the focused code off the
  // right edge, since the camera only translates in y. A focus line too long to
  // fit even at scale 1 cannot be rescued by holding the camera back, so the cap
  // steps aside rather than blocking the framing for every other line.
  const byWidth = maxScaleForWidth(widestFocusLine(lines, a, b));
  const widthCap = byWidth >= 1 ? byWidth : Infinity;
  const maxScale = zooming ? ZOOM_MAX_SCALE : SHOW_MAX_SCALE;
  const scale = snapScale(clamp(Math.min(byHeight, widthCap), 1, maxScale));

  const focusTop = a * LINE_H;
  const focusH = focusLines * LINE_H;
  let y = CODE_VIEW_H / 2 - (focusTop + focusH / 2) * scale;
  const contentH = lines.length * LINE_H * scale;
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
