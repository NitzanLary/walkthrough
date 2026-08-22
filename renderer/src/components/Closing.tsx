import React from "react";
import { AbsoluteFill } from "remotion";
import { CODE_FONT } from "../lib/font";
import type { Chapter } from "../lib/schema";

export const Closing: React.FC<{ chapter: Chapter }> = ({ chapter }) => {
  const bullets = chapter.narration
    .split(/(?<=[.!?])\s+/)
    .filter((s) => s.trim().length > 0)
    .slice(0, 5);
  return (
    <AbsoluteFill
      style={{ backgroundColor: "#181818", color: "#e6e6e6", padding: "160px 200px",
               fontFamily: CODE_FONT }}
    >
      <div style={{ fontSize: 48, fontWeight: 700, marginBottom: 48 }}>{chapter.title}</div>
      {bullets.map((b, i) => (
        <div key={i} style={{ fontSize: 30, lineHeight: 1.6, display: "flex", gap: 20 }}>
          <span style={{ color: "#58a6ff" }}>▪</span>
          <span>{b}</span>
        </div>
      ))}
    </AbsoluteFill>
  );
};
