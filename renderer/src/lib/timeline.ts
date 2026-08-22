import type { Chapter } from "./schema";

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
