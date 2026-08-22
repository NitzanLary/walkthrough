import React, { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender, interpolate, useCurrentFrame } from "remotion";
import { focusIndexRange, type LineKind } from "../lib/diff";
import type { FileEntry, Focus } from "../lib/schema";
import { highlightFile, type HighlightedLine } from "../lib/shiki";
import { diffSide, LINE_H } from "../lib/timeline";

const ROW_BG: Record<LineKind, string> = {
  add: "rgba(46,160,67,0.18)",
  del: "rgba(248,81,73,0.18)",
  ctx: "transparent",
};

export const CodePane: React.FC<{
  file: FileEntry;
  focus: Focus | null;
  dim: boolean;    // true under zoom: non-focused lines at 0.35
  pulse: boolean;  // true under highlight: focus rows pulse
}> = ({ file, focus, dim, pulse }) => {
  const frame = useCurrentFrame();
  const [lines, setLines] = useState<HighlightedLine[] | null>(null);
  const [handle] = useState(() => delayRender(`shiki-${file.path}`));

  useEffect(() => {
    let alive = true;
    highlightFile(file)
      .then((l) => {
        if (alive) setLines(l);
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
    return () => {
      alive = false;
    };
  }, [file, handle]);

  if (!lines) return null;

  const side = diffSide(file.status);
  const [a, b] = focus ? focusIndexRange(lines.map((l) => l.info), focus, side) : [-1, -1];
  const pulseAlpha = pulse
    ? interpolate(Math.sin(frame / 4), [-1, 1], [0.05, 0.3])
    : 0;

  return (
    <div style={{ fontSize: 18, lineHeight: `${LINE_H}px` }}>
      {lines.map((line, i) => {
        const inFocus = i >= a && i <= b;
        return (
          <div
            key={i}
            style={{
              display: "flex", height: LINE_H, whiteSpace: "pre",
              backgroundColor: pulse && inFocus
                ? `rgba(88,166,255,${pulseAlpha})`
                : ROW_BG[line.info.kind],
              opacity: dim && !inFocus ? 0.35 : 1,
              borderLeft: inFocus ? "3px solid #58a6ff" : "3px solid transparent",
            }}
          >
            <span style={{ width: 56, textAlign: "right", color: "#6e7681", flexShrink: 0 }}>
              {line.info.oldNo ?? ""}
            </span>
            <span style={{ width: 56, textAlign: "right", color: "#6e7681",
                           flexShrink: 0, marginRight: 24 }}>
              {line.info.newNo ?? ""}
            </span>
            <span>
              {line.tokens.length === 0
                ? line.info.text
                : line.tokens.map((t, j) => (
                    <span key={j} style={{ color: t.color ?? "#d4d4d4" }}>{t.content}</span>
                  ))}
            </span>
          </div>
        );
      })}
    </div>
  );
};
