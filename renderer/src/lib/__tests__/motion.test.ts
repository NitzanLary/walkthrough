import { describe, expect, it } from "vitest";
import { cameraAt } from "../motion";

const prev = { y: 0, scale: 1 };
const target = { y: -560, scale: 1.4 };

describe("cameraAt", () => {
  it("interpolates from the previous framing when motion is allowed", () => {
    expect(cameraAt(prev, target, 0, false)).toEqual(prev);
    expect(cameraAt(prev, target, 0.5, false)).toEqual({ y: -280, scale: 1.2 });
    expect(cameraAt(prev, target, 1, false)).toEqual(target);
  });

  it("holds the target at every progress under reduced motion", () => {
    for (const p of [0, 0.01, 0.25, 0.5, 0.99, 1]) {
      expect(cameraAt(prev, target, p, true)).toEqual(target);
    }
  });

  it("starts at the target when there is no previous framing", () => {
    expect(cameraAt(null, target, 0, false)).toEqual(target);
  });
});
