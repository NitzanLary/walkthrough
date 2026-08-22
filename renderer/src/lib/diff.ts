import { diffLines } from "diff";
import type { Focus } from "./schema";

export type LineKind = "add" | "del" | "ctx";
export type LineInfo = {
  kind: LineKind;
  oldNo: number | null;
  newNo: number | null;
  text: string;
};

export function computeLineDiff(before: string, after: string): LineInfo[] {
  const out: LineInfo[] = [];
  let oldNo = 1;
  let newNo = 1;
  for (const part of diffLines(before, after)) {
    const lines = part.value.split("\n");
    if (lines[lines.length - 1] === "") lines.pop(); // trailing newline artifact
    for (const text of lines) {
      if (part.added) out.push({ kind: "add", oldNo: null, newNo: newNo++, text });
      else if (part.removed) out.push({ kind: "del", oldNo: oldNo++, newNo: null, text });
      else out.push({ kind: "ctx", oldNo: oldNo++, newNo: newNo++, text });
    }
  }
  return out;
}

export function focusIndexRange(
  lines: LineInfo[],
  focus: Focus,
  side: "old" | "new",
): [number, number] {
  const key = side === "new" ? "newNo" : "oldNo";
  const a = lines.findIndex((l) => l[key] === focus.start);
  const b = lines.findIndex((l) => l[key] === focus.end);
  return [a, b === -1 ? a : b];
}
