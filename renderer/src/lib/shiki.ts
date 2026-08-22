import { createHighlighter, type Highlighter } from "shiki";
import { computeLineDiff, type LineInfo } from "./diff";
import type { FileEntry } from "./schema";

const LANGS = ["python", "go", "typescript", "javascript", "json", "yaml", "markdown", "bash"];

let highlighterPromise: Promise<Highlighter> | null = null;
const getHighlighter = () => {
  highlighterPromise ??= createHighlighter({ themes: ["dark-plus"], langs: LANGS });
  return highlighterPromise;
};

export type HighlightedLine = {
  info: LineInfo;
  tokens: { content: string; color?: string }[];
};

const fileCache = new Map<string, Promise<HighlightedLine[]>>();

async function doHighlight(file: FileEntry): Promise<HighlightedLine[]> {
  const hl = await getHighlighter();
  const lang = file.language && LANGS.includes(file.language) ? file.language : "text";
  const tokensFor = (code: string) =>
    code === ""
      ? []
      : hl.codeToTokensBase(code, { lang: lang as never, theme: "dark-plus" });
  const beforeTokens = tokensFor(file.before);
  const afterTokens = tokensFor(file.after);
  // Diff mixes both sides: del lines take tokens from `before`, others from `after`.
  return computeLineDiff(file.before, file.after).map((info) => {
    const src = info.kind === "del" ? beforeTokens[info.oldNo! - 1] : afterTokens[info.newNo! - 1];
    return {
      info,
      tokens: (src ?? []).map((t) => ({ content: t.content, color: t.color })),
    };
  });
}

export function highlightFile(file: FileEntry): Promise<HighlightedLine[]> {
  if (!fileCache.has(file.path)) fileCache.set(file.path, doHighlight(file));
  return fileCache.get(file.path)!;
}
