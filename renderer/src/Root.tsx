import React from "react";
import { Composition, staticFile } from "remotion";
import { Walkthrough } from "./Walkthrough";
import { WalkthroughSchema, type Walkthrough as WT } from "./lib/schema";
import { buildTimeline, totalFrames } from "./lib/timeline";

export const FPS = 30;

export const Root: React.FC = () => (
  <Composition
    id="Walkthrough"
    component={Walkthrough}
    width={1920}
    height={1080}
    fps={FPS}
    durationInFrames={300}
    defaultProps={{ data: null as unknown as WT }}
    calculateMetadata={async () => {
      const res = await fetch(staticFile("walkthrough.json"));
      const data = WalkthroughSchema.parse(await res.json());
      return {
        durationInFrames: Math.max(1, totalFrames(buildTimeline(data.chapters, FPS))),
        props: { data },
      };
    }}
  />
);
