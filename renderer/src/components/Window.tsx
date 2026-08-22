import React from "react";
import { CODE_FONT } from "../lib/font";
import { CODE_VIEW_H, CODE_VIEW_W } from "../lib/timeline";
import type { FileEntry } from "../lib/schema";

const STATUS_COLOR: Record<FileEntry["status"], string> = {
  added: "#2ea043",
  modified: "#d29922",
  deleted: "#f85149",
  renamed: "#58a6ff",
};

export const Window: React.FC<{ file: FileEntry; children: React.ReactNode }> = ({
  file,
  children,
}) => (
  <div
    style={{
      width: CODE_VIEW_W,
      margin: "80px auto 0",
      borderRadius: 12,
      overflow: "hidden",
      backgroundColor: "#1f1f1f",
      boxShadow: "0 24px 80px rgba(0,0,0,0.55)",
      fontFamily: CODE_FONT,
    }}
  >
    <div
      style={{
        height: 48, display: "flex", alignItems: "center", gap: 8,
        padding: "0 16px", backgroundColor: "#181818",
        borderBottom: "1px solid #2b2b2b",
      }}
    >
      {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
        <div key={c} style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: c }} />
      ))}
      <div
        style={{
          marginLeft: 16, padding: "6px 14px", backgroundColor: "#1f1f1f",
          borderRadius: "8px 8px 0 0", color: "#cccccc", fontSize: 16,
          display: "flex", alignItems: "center", gap: 8,
        }}
      >
        {file.path}
        <div
          style={{
            width: 8, height: 8, borderRadius: 4,
            backgroundColor: STATUS_COLOR[file.status],
          }}
        />
      </div>
    </div>
    <div style={{ height: CODE_VIEW_H, overflow: "hidden", position: "relative" }}>
      {children}
    </div>
  </div>
);
