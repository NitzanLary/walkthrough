import { describe, expect, it } from "vitest";
import { MAX_CUE_CHARS, buildCues, cueAt, splitNarration } from "../captions";
import { buildTimeline } from "../timeline";

const chapter = (id: string, narration: string, duration_ms: number) =>
  ({ id, narration, audio: { path: `audio/${id}.mp3`, duration_ms } }) as never;

describe("splitNarration", () => {
  it("splits on sentence boundaries and keeps the terminator", () => {
    expect(splitNarration("One thing. Then another! Why? ")).toEqual([
      "One thing.",
      "Then another!",
      "Why?",
    ]);
  });

  it("wraps a sentence too long for one cue at word boundaries", () => {
    const long = `${"word ".repeat(40).trim()}.`;
    const cues = splitNarration(long);
    expect(cues.length).toBeGreaterThan(1);
    for (const c of cues) expect(c.length).toBeLessThanOrEqual(MAX_CUE_CHARS);
    expect(cues.join(" ")).toBe(long);
  });

  it("has nothing to say about empty narration", () => {
    expect(splitNarration("   ")).toEqual([]);
  });
});

describe("buildCues", () => {
  const chapters = [
    chapter("c1", "First sentence. Second one here.", 4000),
    chapter("c2", "Only one.", 2000),
  ];
  const timeline = buildTimeline(chapters, 30);
  const cues = buildCues(chapters, timeline, 30);

  it("tiles each chapter's audio with no gap and no overlap", () => {
    const first = cues.filter((c) => c.chapterIndex === 0);
    expect(first).toHaveLength(2);
    expect(first[0].from).toBe(timeline[0].from);
    expect(first[1].from).toBe(first[0].from + first[0].durationInFrames);
    const end = first[1].from + first[1].durationInFrames;
    expect(end).toBe(timeline[0].from + 120); // 4000ms at 30fps
  });

  it("stops before the chapter's trailing silence", () => {
    const last = cues[cues.length - 1];
    const t = timeline[1];
    expect(last.from + last.durationInFrames).toBeLessThan(t.from + t.durationInFrames);
  });

  it("longer text gets the longer slot", () => {
    const [a, b] = cues;
    expect(b.text.length).toBeGreaterThan(a.text.length);
    expect(b.durationInFrames).toBeGreaterThan(a.durationInFrames);
  });
});

describe("cueAt", () => {
  const chapters = [chapter("c1", "First sentence. Second one here.", 4000)];
  const cues = buildCues(chapters, buildTimeline(chapters, 30), 30);

  it("returns the cue covering the frame", () => {
    expect(cueAt(cues, 0)?.text).toBe("First sentence.");
    expect(cueAt(cues, 119)?.text).toBe("Second one here.");
  });

  it("returns null once the narration is over", () => {
    expect(cueAt(cues, 120)).toBeNull();
  });
});
