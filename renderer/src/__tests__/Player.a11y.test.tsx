// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The Remotion player needs a canvas and audio; the shell around it is what
// these tests are about, so it is replaced by a ref-compatible stub.
const player = vi.hoisted(() => ({
  seekTo: vi.fn(),
  toggle: vi.fn(),
  play: vi.fn(),
  pause: vi.fn(),
  mute: vi.fn(),
  unmute: vi.fn(),
  isMuted: vi.fn(() => false),
  isPlaying: vi.fn(() => false),
  getCurrentFrame: vi.fn(() => 0),
  requestFullscreen: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
}));

vi.mock("@remotion/player", async () => {
  const react = await import("react");
  return {
    Player: react.forwardRef((_props: Record<string, unknown>, ref) => {
      react.useImperativeHandle(ref, () => player);
      return react.createElement("div", { "data-testid": "stage" });
    }),
  };
});

import fixture from "../fixtures/walkthrough.json";
import { PlayerPage } from "../Player";
import { FPS } from "../Root";
import { buildTimeline } from "../lib/timeline";

const timeline = buildTimeline(fixture.chapters as never, FPS);

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ json: async () => fixture })),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function renderPlayer() {
  const utils = render(<PlayerPage />);
  await screen.findByRole("navigation", { name: "Chapters" });
  return utils;
}

describe("player shell accessibility", () => {
  it("has no automatically detectable accessibility violations", async () => {
    const { container } = await renderPlayer();
    const results = await axe.run(container, {
      runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
      // The test mounts the shell into a bare container rather than a document,
      // so landmark-completeness rules have nothing to judge.
      rules: { region: { enabled: false } },
    });
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });

  it("announces loading and load failures", async () => {
    render(<PlayerPage />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
    cleanup();
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("boom"))));
    render(<PlayerPage />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("boom"));
  });
});

describe("chapter navigation without a mouse", () => {
  it("renders chapters as buttons in a list and marks the current one", async () => {
    await renderPlayer();
    const nav = screen.getByRole("navigation", { name: "Chapters" });
    const buttons = within(nav).getAllByRole("button");
    expect(buttons).toHaveLength(fixture.chapters.length);
    expect(buttons[0].getAttribute("aria-current")).toBe("true");
    expect(buttons[1].getAttribute("aria-current")).toBeNull();
  });

  it("every chapter button is reachable by tab and seeks when activated", async () => {
    await renderPlayer();
    const nav = screen.getByRole("navigation", { name: "Chapters" });
    const third = within(nav).getAllByRole("button")[2];
    third.focus();
    expect(document.activeElement).toBe(third);
    fireEvent.click(third); // what Enter and Space do to a native button
    expect(player.seekTo).toHaveBeenCalledWith(timeline[2].from);
  });
});

describe("keyboard shortcuts", () => {
  const press = (key: string) =>
    fireEvent.keyDown(screen.getByTestId("stage"), { key });

  it("plays, seeks, and moves between chapters from the keyboard", async () => {
    await renderPlayer();
    press("k");
    expect(player.toggle).toHaveBeenCalledTimes(1);

    press("ArrowRight");
    expect(player.seekTo).toHaveBeenLastCalledWith(5 * FPS);
    press("l");
    expect(player.seekTo).toHaveBeenLastCalledWith(10 * FPS);
    press("ArrowLeft");
    expect(player.seekTo).toHaveBeenLastCalledWith(0); // clamped at the start

    press("n");
    expect(player.seekTo).toHaveBeenLastCalledWith(timeline[1].from);
    press("End");
    expect(player.seekTo).toHaveBeenLastCalledWith(timeline[timeline.length - 1].from);
    press("Home");
    expect(player.seekTo).toHaveBeenLastCalledWith(0);
  });

  it("changes speed and toggles captions and mute", async () => {
    await renderPlayer();
    const speed = screen.getByLabelText(/speed/i) as HTMLSelectElement;
    expect(speed.value).toBe("1");
    press(".");
    expect(speed.value).toBe("1.25");
    press(",");
    expect(speed.value).toBe("1");

    const captions = screen.getByRole("button", { name: "Captions" });
    expect(captions.getAttribute("aria-pressed")).toBe("true");
    press("c");
    expect(captions.getAttribute("aria-pressed")).toBe("false");

    press("m");
    expect(player.mute).toHaveBeenCalledTimes(1);
  });

  it("leaves space to the control that has focus", async () => {
    await renderPlayer();
    const play = screen.getByRole("button", { name: "Play" });
    fireEvent.keyDown(play, { key: " " });
    expect(player.toggle).not.toHaveBeenCalled();
  });
});

describe("captions and transcript", () => {
  it("shows the first cue of the current chapter by default", async () => {
    await renderPlayer();
    const captions = screen.getByRole("region", { name: "Captions" });
    expect(fixture.chapters[0].narration).toContain(captions.textContent!.trim());
  });

  it("carries the full narration of every chapter in the transcript", async () => {
    await renderPlayer();
    const transcript = screen.getByRole("region", { name: "Transcript" });
    for (const ch of fixture.chapters) {
      expect(transcript.textContent).toContain(ch.narration);
    }
  });
});
