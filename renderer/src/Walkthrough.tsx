import React from "react";
import { AbsoluteFill } from "remotion";
import type { Walkthrough as WT } from "./lib/schema";

export const Walkthrough: React.FC<{ data: WT }> = ({ data }) => (
  <AbsoluteFill style={{ backgroundColor: "#1f1f1f", color: "#ccc",
                         justifyContent: "center", alignItems: "center",
                         fontFamily: "monospace", fontSize: 48 }}>
    {data ? data.meta.title : "no data"}
  </AbsoluteFill>
);
