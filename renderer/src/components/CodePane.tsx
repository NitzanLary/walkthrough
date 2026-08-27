import React, { useEffect, useMemo, useState } from "react";
import { cancelRender, continueRender, delayRender, interpolate, useCurrentFrame } from "remotion";
import { focusIndexRange, type LineKind } from "../lib/diff";
import type { FileEntry, Focus } from "../lib/schema";
import { highlightFile, type HighlightedLine } from "../lib/shiki";
import { CHAR_W, diffSide, LINE_H, WRAP_COLS } from "../lib/timeline";
import { CONT_INDENT, wrapLines } from "../lib/wrap";

const ROW_BG: Record<LineKind, string> = {
  add: "rgba(46,160,67,0.18)",
  del: "rgba(248,81,73,0.18)",
  ctx: "transparent",
};

type Token = HighlightedLine["tokens"][number];

/** The tokens covering [from, to) of a line, splitting any token that straddles. */
function sliceTokens(tokens: Token[], from: number, to: number): Token[] {
  const out: Token[] = [];
  let pos = 0;
  for (const t of tokens) {
    const s = Math.max(from, pos);
    const e = Math.min(to, pos + t.content.length);
    if (e > s) out.push({ content: t.content.slice(s - pos, e - pos), color: t.color });
    pos += t.content.length;
  }
  return out;
}

export const CodePane: React.FC<{
  file: FileEntry;
  focus: Focus | null;
  dim: number;     // opacity of the rows outside the focus range (1 = no dim)
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

  // The layout is fixed for the file, so it is built once rather than per frame.
  const layout = useMemo(() => {
    if (!lines) return null;
    const infos = lines.map((l) => l.info);
    return { infos, ...wrapLines(infos, WRAP_COLS) };
  }, [lines]);

  if (!lines || !layout) return null;

  const side = diffSide(file.status);
  const [a, b] = focus ? focusIndexRange(layout.infos, focus, side) : [-1, -1];
  // Focus bounds are rows, not lines: a wrapped line is focused across all of its.
  const [from, to] = a < 0
    ? [-1, -1]
    : [layout.startOf[a], layout.startOf[Math.min(b, layout.infos.length - 1) + 1] - 1];
  // With no focus range there is nothing to dim against — every row is equal.
  const dimOpacity = focus ? dim : 1;
  const pulseAlpha = pulse
    ? interpolate(Math.sin(frame / 4), [-1, 1], [0.05, 0.3])
    : 0;

  return (
    <div style={{ fontSize: 18, lineHeight: `${LINE_H}px` }}>
      {layout.rows.map((row, i) => {
        const line = lines[row.src];
        const inFocus = i >= from && i <= to;
        return (
          <div
            key={i}
            style={{
              display: "flex", height: LINE_H, whiteSpace: "pre",
              backgroundColor: pulse && inFocus
                ? `rgba(88,166,255,${pulseAlpha})`
                : ROW_BG[line.info.kind],
              opacity: inFocus ? 1 : dimOpacity,
              borderLeft: inFocus ? "3px solid #58a6ff" : "3px solid transparent",
            }}
          >
            <span style={{ width: 56, textAlign: "right", color: "#6e7681", flexShrink: 0 }}>
              {row.cont ? "" : line.info.oldNo ?? ""}
            </span>
            <span style={{ width: 56, textAlign: "right", color: "#6e7681",
                           flexShrink: 0, marginRight: 24 }}>
              {row.cont ? "" : line.info.newNo ?? ""}
            </span>
            <span style={{ paddingLeft: row.cont ? CONT_INDENT * CHAR_W : 0 }}>
              {line.tokens.length === 0
                ? row.text
                : sliceTokens(line.tokens, row.start, row.start + row.text.length).map((t, j) => (
                    <span key={j} style={{ color: t.color ?? "#d4d4d4" }}>{t.content}</span>
                  ))}
            </span>
          </div>
        );
      })}
    </div>
  );
};
