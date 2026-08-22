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
export const CODE_VIEW_H = 872; // 920px window minus 48px tab bar

export type CameraTarget = { y: number; scale: number };

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function cameraTarget(
  lines: LineInfo[],
  focus: Focus,
  action: Action,
  side: "old" | "new",
): CameraTarget {
  const [a, b] = focusIndexRange(lines, focus, side);
  const focusLines = b - a + 1;
  const scale =
    action === "zoom" ? clamp(CODE_VIEW_H / (focusLines * LINE_H * 1.4), 1, 2.2) : 1;
  const focusTop = a * LINE_H;
  const focusH = focusLines * LINE_H;
  let y = CODE_VIEW_H / 2 - (focusTop + focusH / 2) * scale;
  const contentH = lines.length * LINE_H * scale;
  const minY = Math.min(0, CODE_VIEW_H - contentH);
  y = clamp(y, minY, 0);
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
