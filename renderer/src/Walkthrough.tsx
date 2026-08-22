import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, Sequence, staticFile, useVideoConfig } from "remotion";
import { Camera } from "./components/Camera";
import { Closing } from "./components/Closing";
import { CodePane } from "./components/CodePane";
import { LowerThird } from "./components/LowerThird";
import { Overview } from "./components/Overview";
import { Window } from "./components/Window";
import type { Chapter, Walkthrough as WT } from "./lib/schema";
import { buildTimeline, chapterTargets, type CameraTarget } from "./lib/timeline";

const CodeChapter: React.FC<{
  data: WT;
  chapter: Chapter;
  prev: CameraTarget | null;
  target: CameraTarget;
}> = ({ data, chapter, prev, target }) => {
  const file = data.files.find((f) => f.path === chapter.file)!;
  return (
    <Window file={file}>
      <Camera prev={prev} target={target}>
        <CodePane
          file={file}
          focus={chapter.focus ?? null}
          dim={chapter.action === "zoom"}
          pulse={chapter.action === "highlight"}
        />
      </Camera>
    </Window>
  );
};

export const Walkthrough: React.FC<{ data: WT }> = ({ data }) => {
  const { fps } = useVideoConfig();
  if (!data) return <AbsoluteFill style={{ backgroundColor: "#1f1f1f" }} />;
  const timeline = buildTimeline(data.chapters, fps);
  const targets = chapterTargets(data);

  return (
    <AbsoluteFill style={{ backgroundColor: "#181818" }}>
      {data.chapters.map((ch, i) => {
        const t = timeline[i];
        // Spring starts from the previous chapter's target only when it showed
        // the same file (scroll/highlight continuity); otherwise from top.
        const samePrevFile = i > 0 && data.chapters[i - 1].file === ch.file;
        const prev = samePrevFile ? targets[i - 1] : { y: 0, scale: 1 };
        return (
          <Sequence key={ch.id} from={t.from} durationInFrames={t.durationInFrames}>
            <Audio src={staticFile(ch.audio.path)} />
            {ch.action === "overview" ? (
              <Overview data={data} />
            ) : ch.action === "closing" ? (
              <Closing chapter={ch} />
            ) : (
              <CodeChapter data={data} chapter={ch} prev={prev} target={targets[i]!} />
            )}
            <LowerThird title={ch.title} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
