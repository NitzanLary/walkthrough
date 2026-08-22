import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { CameraTarget } from "../lib/timeline";

export const Camera: React.FC<{
  prev: CameraTarget | null;
  target: CameraTarget;
  children: React.ReactNode;
}> = ({ prev, target, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const from = prev ?? target;
  const p = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 20 });
  const y = interpolate(p, [0, 1], [from.y, target.y]);
  const scale = interpolate(p, [0, 1], [from.scale, target.scale]);
  // Individual CSS transform properties (official markup guidance); CSS applies
  // translate before scale, matching the previous translateY()+scale() string.
  return (
    <div style={{ translate: `0px ${y}px`, scale: `${scale}`, transformOrigin: "top left" }}>
      {children}
    </div>
  );
};
