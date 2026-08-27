/** Caption cues derived from the narration text a chapter was synthesized from.
 *
 * The provider's word alignment is not available here: `narrate` caches clips
 * by text, and the cache keeps only the mp3 and its duration, so a cached
 * chapter has no `.words.json`. Cues therefore split the narration at sentence
 * boundaries and share out the chapter's audio duration by character count,
 * which is the same assumption the fake narrator makes about pace. */
import type { Chapter } from "./schema";
import type { ChapterTiming } from "./timeline";

export type Cue = {
  chapterIndex: number;
  text: string;
  from: number;
  durationInFrames: number;
};

// Long enough for a whole short sentence, short enough that a cue stays within
// two lines in the caption bar.
export const MAX_CUE_CHARS = 90;

function wrap(sentence: string): string[] {
  if (sentence.length <= MAX_CUE_CHARS) return [sentence];
  const parts: string[] = [];
  let line = "";
  for (const word of sentence.split(/\s+/)) {
    if (line && `${line} ${word}`.length > MAX_CUE_CHARS) {
      parts.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) parts.push(line);
  return parts;
}

export function splitNarration(narration: string): string[] {
  const out: string[] = [];
  for (const raw of narration.match(/[^.!?]+[.!?]*/g) ?? []) {
    const sentence = raw.trim();
    if (sentence) out.push(...wrap(sentence));
  }
  return out;
}

/** Cues for the whole walkthrough, in frame order.
 *
 * A cue never runs past its chapter's audio: `buildTimeline` pads each chapter
 * with 15 frames of silence at the end, and captions should be gone by then. */
export function buildCues(
  chapters: Chapter[],
  timeline: ChapterTiming[],
  fps: number,
): Cue[] {
  const cues: Cue[] = [];
  chapters.forEach((ch, chapterIndex) => {
    const t = timeline[chapterIndex];
    const texts = splitNarration(ch.narration);
    if (texts.length === 0) return;
    const span = Math.min(
      Math.round((ch.audio.duration_ms / 1000) * fps),
      t.durationInFrames,
    );
    const chars = texts.reduce((n, s) => n + s.length, 0);
    let used = 0;
    texts.forEach((text, i) => {
      // The last cue absorbs the rounding, so the cues tile the span exactly.
      const durationInFrames =
        i === texts.length - 1
          ? Math.max(0, span - used)
          : Math.max(1, Math.round((text.length / chars) * span));
      cues.push({ chapterIndex, text, from: t.from + used, durationInFrames });
      used += durationInFrames;
    });
  });
  return cues;
}

export function cueAt(cues: Cue[], frame: number): Cue | null {
  return (
    cues.find((c) => frame >= c.from && frame < c.from + c.durationInFrames) ?? null
  );
}
