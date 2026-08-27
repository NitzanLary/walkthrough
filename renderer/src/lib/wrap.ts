import type { LineInfo } from "./diff";

// Characters a continuation row is indented, so a wrapped line still reads as one.
export const CONT_INDENT = 2;

export type VisualRow = {
  /** Index of the source line in the diff this row is a segment of. */
  src: number;
  text: string;
  /** Character offset of this segment within the source line. */
  start: number;
  cont: boolean;
};

export type WrappedFile = {
  rows: VisualRow[];
  /** First visual row of each source line; the final entry is the total row count. */
  startOf: number[];
};

/**
 * Split a source line into segments of at most `cols` characters. The camera only
 * translates in y, so anything past the right edge is lost rather than reachable
 * — a line wider than the window has to become more rows, not a wider row.
 */
export function wrapText(text: string, cols: number): string[] {
  if (text.length <= cols) return [text];
  const out = [text.slice(0, cols)];
  const width = Math.max(1, cols - CONT_INDENT);
  for (let i = cols; i < text.length; i += width) out.push(text.slice(i, i + width));
  return out;
}

/** Lay the diff out as fixed-height rows, wrapping any line too wide for the window. */
export function wrapLines(lines: LineInfo[], cols: number): WrappedFile {
  const rows: VisualRow[] = [];
  const startOf: number[] = [];
  lines.forEach((line, src) => {
    startOf.push(rows.length);
    let start = 0;
    wrapText(line.text, cols).forEach((text, i) => {
      rows.push({ src, text, start, cont: i > 0 });
      start += text.length;
    });
  });
  startOf.push(rows.length);
  return { rows, startOf };
}
