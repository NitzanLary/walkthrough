import { Player, type PlayerRef } from "@remotion/player";
import React, { useEffect, useRef, useState } from "react";
import { FPS } from "./Root";
import { Walkthrough } from "./Walkthrough";
import { WalkthroughSchema, type Walkthrough as WT } from "./lib/schema";
import { buildTimeline, totalFrames } from "./lib/timeline";

export const PlayerPage: React.FC = () => {
  const [data, setData] = useState<WT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<PlayerRef>(null);

  useEffect(() => {
    fetch("/walkthrough.json")
      .then((r) => r.json())
      .then((j) => setData(WalkthroughSchema.parse(j)))
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div style={{ padding: 40, color: "#f85149" }}>{error}</div>;
  if (!data) return <div style={{ padding: 40 }}>loading…</div>;

  const timeline = buildTimeline(data.chapters, FPS);
  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <div style={{ width: 320, overflowY: "auto", borderRight: "1px solid #2b2b2b",
                    padding: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>
          {data.meta.title}
        </div>
        {data.chapters.map((ch, i) => (
          <div
            key={ch.id}
            onClick={() => ref.current?.seekTo(timeline[i].from)}
            style={{ padding: "10px 12px", cursor: "pointer", borderRadius: 6,
                     fontSize: 14, color: "#cccccc" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#252525")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {i + 1}. {ch.title}
          </div>
        ))}
      </div>
      <div style={{ flex: 1, display: "flex", alignItems: "center",
                    justifyContent: "center", padding: 24 }}>
        <Player
          ref={ref}
          component={Walkthrough}
          inputProps={{ data }}
          durationInFrames={Math.max(1, totalFrames(timeline))}
          fps={FPS}
          compositionWidth={1920}
          compositionHeight={1080}
          controls
          style={{ width: "100%", maxWidth: 1280 }}
        />
      </div>
    </div>
  );
};
