import { describe, expect, it } from "vitest";
import fixture from "../../fixtures/walkthrough.json";
import { WalkthroughSchema } from "../schema";

describe("WalkthroughSchema", () => {
  it("accepts the committed fixture", () => {
    expect(() => WalkthroughSchema.parse(fixture)).not.toThrow();
  });

  it("rejects a code chapter without focus", () => {
    const bad = structuredClone(fixture) as never as typeof fixture;
    (bad.chapters[1] as { focus: unknown }).focus = null;
    expect(() => WalkthroughSchema.parse(bad)).toThrow(/require file and focus/);
  });

  it("rejects an overview chapter carrying a file", () => {
    const bad = structuredClone(fixture) as never as typeof fixture;
    (bad.chapters[0] as { file: unknown }).file = "api/app.py";
    expect(() => WalkthroughSchema.parse(bad)).toThrow(/carry no file\/focus/);
  });
});
