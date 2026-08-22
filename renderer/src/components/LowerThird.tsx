import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { CODE_FONT } from "../lib/font";

export const LowerThird: React.FC<{ title: string }> = ({ title }) => {
  const frame = useCurrentFrame();
  if (frame > 90) return null;
  const opacity = interpolate(frame, [0, 10, 75, 90], [0, 1, 1, 0]);
  return (
    <div
      style={{
        position: "absolute", left: 160, bottom: 48, opacity,
        backgroundColor: "rgba(24,24,24,0.9)", border: "1px solid #2b2b2b",
        borderRadius: 8, padding: "12px 24px", color: "#e6e6e6",
        fontFamily: CODE_FONT, fontSize: 28,
      }}
    >
      {title}
    </div>
  );
};
