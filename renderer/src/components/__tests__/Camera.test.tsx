// @vitest-environment jsdom
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

// A linear stand-in for the spring: the assertion is about what the camera does
// with the progress, not about the easing curve.
vi.mock("remotion", () => ({
  useCurrentFrame: () => state.frame,
  useVideoConfig: () => ({ fps: 30 }),
  spring: ({ frame }: { frame: number }) => Math.min(1, Math.max(0, frame / 20)),
}));

const state = vi.hoisted(() => ({ frame: 0 }));

import { Camera } from "../Camera";

function setReducedMotion(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: () => ({ matches, addEventListener() {}, removeEventListener() {} }),
  });
}

const prev = { y: 0, scale: 1 };
const target = { y: -560, scale: 1.4 };

/** The transform Camera renders at `frame`, read off the markup. */
function transformAt(frame: number): string {
  state.frame = frame;
  const html = renderToStaticMarkup(
    <Camera prev={prev} target={target}>
      <span />
    </Camera>,
  );
  return /style="([^"]*)"/.exec(html)![1];
}

afterEach(() => {
  state.frame = 0;
});

describe("Camera", () => {
  it("pans and zooms across the transition by default", () => {
    setReducedMotion(false);
    expect(transformAt(0)).toContain("translate:0px 0px");
    expect(transformAt(0)).toContain("scale:1");
    expect(transformAt(10)).toContain("translate:0px -280px");
    expect(transformAt(20)).toContain("translate:0px -560px");
  });

  it("cuts straight to the framing under prefers-reduced-motion", () => {
    setReducedMotion(true);
    for (const frame of [0, 1, 5, 10, 19, 20, 60]) {
      const style = transformAt(frame);
      expect(style).toContain("translate:0px -560px");
      expect(style).toContain("scale:1.4");
    }
  });
});
