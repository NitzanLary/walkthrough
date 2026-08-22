import React from "react";
import { AbsoluteFill } from "remotion";
import { CODE_FONT } from "../lib/font";
import type { Walkthrough as WT } from "../lib/schema";

const MAX_TREE = 30;

const Chip: React.FC<{ label: string; color: string }> = ({ label, color }) => (
  <span style={{ padding: "6px 16px", borderRadius: 20, border: `1px solid ${color}`,
                 color, fontSize: 22 }}>{label}</span>
);

export const Overview: React.FC<{ data: WT }> = ({ data }) => {
  const shown = data.files.slice(0, MAX_TREE);
  const extra = data.files.length - shown.length;
  return (
    <AbsoluteFill
      style={{ backgroundColor: "#181818", color: "#e6e6e6", padding: "120px 160px",
               fontFamily: CODE_FONT }}
    >
      <div style={{ fontSize: 56, fontWeight: 700 }}>{data.meta.title}</div>
      <div style={{ fontSize: 26, color: "#9d9d9d", marginTop: 24, maxWidth: 1200,
                    lineHeight: 1.5 }}>
        {data.meta.summary}
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 40 }}>
        <Chip label={`${data.meta.stats.files} files`} color="#58a6ff" />
        <Chip label={`+${data.meta.stats.added}`} color="#2ea043" />
        <Chip label={`−${data.meta.stats.removed}`} color="#f85149" />
      </div>
      <div style={{ marginTop: 48, fontSize: 22, color: "#cccccc",
                    columnCount: 2, columnGap: 80 }}>
        {shown.map((f) => (
          <div key={f.path} style={{ padding: "4px 0" }}>{f.path}</div>
        ))}
        {extra > 0 && <div style={{ color: "#6e7681" }}>+{extra} more</div>}
      </div>
    </AbsoluteFill>
  );
};
