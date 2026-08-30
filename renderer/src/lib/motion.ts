import { useEffect, useState } from "react";
import type { CameraTarget } from "./timeline";

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(REDUCED_MOTION_QUERY).matches
  );
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(REDUCED_MOTION_QUERY);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/**
 * Where the camera sits at spring progress `p`.
 *
 * Under reduced motion the pan/zoom becomes a cut: the chapter opens already
 * framed on its focus, so the code never travels across the screen. Framing is
 * unchanged — only the trip between two framings is dropped.
 */
export function cameraAt(
  prev: CameraTarget | null,
  target: CameraTarget,
  p: number,
  reduced: boolean,
): CameraTarget {
  const from = reduced ? target : prev ?? target;
  return {
    y: from.y + (target.y - from.y) * p,
    scale: from.scale + (target.scale - from.scale) * p,
  };
}
