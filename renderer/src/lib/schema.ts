import { z } from "zod";

export const FocusSchema = z.object({
  start: z.number().int().min(1),
  end: z.number().int().min(1),
  anchor: z.string(),
});

export const FileSchema = z.object({
  path: z.string(),
  language: z.string().nullish(),
  status: z.enum(["added", "modified", "deleted", "renamed"]),
  old_path: z.string().nullish(),
  before: z.string(),
  after: z.string(),
});

export const AudioSchema = z.object({
  path: z.string(),
  duration_ms: z.number().int().positive(),
});

export const ChapterSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    action: z.enum(["overview", "show", "scroll", "zoom", "highlight", "closing"]),
    file: z.string().nullish(),
    focus: FocusSchema.nullish(),
    narration: z.string(),
    audio: AudioSchema,
  })
  .superRefine((ch, ctx) => {
    const bookend = ch.action === "overview" || ch.action === "closing";
    if (bookend && (ch.file != null || ch.focus != null)) {
      ctx.addIssue({ code: "custom", message: `${ch.id}: ${ch.action} chapters carry no file/focus` });
    }
    if (!bookend && (ch.file == null || ch.focus == null)) {
      ctx.addIssue({ code: "custom", message: `${ch.id}: ${ch.action} chapters require file and focus` });
    }
  });

export const WalkthroughSchema = z.object({
  version: z.literal(1),
  meta: z.object({
    repo: z.string(),
    base: z.string(),
    head: z.string(),
    base_sha: z.string(),
    head_sha: z.string(),
    title: z.string(),
    summary: z.string(),
    stats: z.object({ files: z.number(), added: z.number(), removed: z.number() }),
    skipped: z.array(z.string()),
    generated_at: z.string(),
  }),
  files: z.array(FileSchema),
  chapters: z.array(ChapterSchema),
});

export type Walkthrough = z.infer<typeof WalkthroughSchema>;
export type Chapter = z.infer<typeof ChapterSchema>;
export type FileEntry = z.infer<typeof FileSchema>;
export type Focus = z.infer<typeof FocusSchema>;
export type AudioRef = z.infer<typeof AudioSchema>;
export type Action = Chapter["action"];
