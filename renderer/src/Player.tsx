import { Player, type PlayerRef } from "@remotion/player";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FPS } from "./Root";
import { Walkthrough } from "./Walkthrough";
import { buildCues, cueAt } from "./lib/captions";
import { WalkthroughSchema, type Walkthrough as WT } from "./lib/schema";
import { buildTimeline, chapterIndexAt, totalFrames } from "./lib/timeline";
import "./player.css";

const SEEK_SMALL_S = 5;
const SEEK_LARGE_S = 10;
export const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

function formatTime(frames: number, fps: number): string {
  const total = Math.max(0, Math.round(frames / fps));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Keys typed into a field belong to the field, never to playback. */
function isTextEntry(el: EventTarget | null): boolean {
  return (
    el instanceof HTMLElement &&
    (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA")
  );
}

export const PlayerPage: React.FC = () => {
  const [data, setData] = useState<WT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [captionsOn, setCaptionsOn] = useState(true);
  const [status, setStatus] = useState("");
  const ref = useRef<PlayerRef>(null);

  useEffect(() => {
    fetch("/walkthrough.json")
      .then((r) => r.json())
      .then((j) => setData(WalkthroughSchema.parse(j)))
      .catch((e) => setError(String(e)));
  }, []);

  // Playback state drives the caption, the current chapter, and what the status
  // region announces, so it is mirrored into React state rather than polled.
  useEffect(() => {
    const player = ref.current;
    if (!player) return;
    const onFrame = (e: { detail: { frame: number } }) => setFrame(e.detail.frame);
    const onPlay = () => {
      setPlaying(true);
      setStatus("Playing");
    };
    const onPause = () => {
      setPlaying(false);
      setStatus("Paused");
    };
    const onMute = (e: { detail: { isMuted: boolean } }) => setMuted(e.detail.isMuted);
    const onError = (e: { detail: { error: Error } }) => setError(String(e.detail.error));
    player.addEventListener("frameupdate", onFrame);
    player.addEventListener("play", onPlay);
    player.addEventListener("pause", onPause);
    player.addEventListener("mutechange", onMute);
    player.addEventListener("error", onError);
    return () => {
      player.removeEventListener("frameupdate", onFrame);
      player.removeEventListener("play", onPlay);
      player.removeEventListener("pause", onPause);
      player.removeEventListener("mutechange", onMute);
      player.removeEventListener("error", onError);
    };
  }, [data]);

  const timeline = useMemo(
    () => (data ? buildTimeline(data.chapters, FPS) : []),
    [data],
  );
  const cues = useMemo(
    () => (data ? buildCues(data.chapters, timeline, FPS) : []),
    [data, timeline],
  );
  const duration = Math.max(1, totalFrames(timeline));
  const active = chapterIndexAt(timeline, frame);
  const caption = captionsOn ? cueAt(cues, frame)?.text ?? "" : "";

  const seekTo = useCallback((f: number) => {
    const clamped = Math.max(0, Math.min(duration - 1, Math.round(f)));
    ref.current?.seekTo(clamped);
    setFrame(clamped);
  }, [duration]);

  const seekBy = useCallback((seconds: number) => {
    seekTo((ref.current?.getCurrentFrame() ?? frame) + seconds * FPS);
  }, [frame, seekTo]);

  const goToChapter = useCallback((i: number) => {
    if (!data) return;
    const index = Math.max(0, Math.min(data.chapters.length - 1, i));
    seekTo(timeline[index].from);
    setStatus(`Chapter ${index + 1} of ${data.chapters.length}: ${data.chapters[index].title}`);
  }, [data, seekTo, timeline]);

  const toggle = useCallback(() => {
    // The status text comes from the play/pause events, not from here: those
    // also fire when playback ends or starts on its own.
    ref.current?.toggle();
  }, []);

  const toggleMute = useCallback(() => {
    const player = ref.current;
    if (!player) return;
    if (player.isMuted()) player.unmute();
    else player.mute();
  }, []);

  const stepSpeed = useCallback((direction: 1 | -1) => {
    setSpeed((current) => {
      const i = SPEEDS.indexOf(current);
      const next = SPEEDS[Math.max(0, Math.min(SPEEDS.length - 1, i + direction))];
      setStatus(`Speed ${next}×`);
      return next;
    });
  }, []);

  // On the document, not the shell: nothing is focused when the page loads, so
  // a handler mounted on the container would never see the first key. Capture
  // phase so a handled key is swallowed before anything else can act on it.
  const onKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (isTextEntry(e.target)) return;
    const key = e.key;
    const handled = () => {
      e.preventDefault();
      e.stopPropagation();
    };
    switch (key) {
      case " ":
        // Space belongs to whatever button has focus.
        if (e.target instanceof HTMLElement && e.target.closest("button, a")) return;
        handled();
        toggle();
        return;
      case "k":
        handled();
        toggle();
        return;
      case "ArrowLeft":
        handled();
        seekBy(-SEEK_SMALL_S);
        return;
      case "ArrowRight":
        handled();
        seekBy(SEEK_SMALL_S);
        return;
      case "j":
        handled();
        seekBy(-SEEK_LARGE_S);
        return;
      case "l":
        handled();
        seekBy(SEEK_LARGE_S);
        return;
      case "p":
        handled();
        goToChapter(active - 1);
        return;
      case "n":
        handled();
        goToChapter(active + 1);
        return;
      case "Home":
        handled();
        goToChapter(0);
        return;
      case "End":
        handled();
        goToChapter(timeline.length - 1);
        return;
      case ",":
      case "<":
        handled();
        stepSpeed(-1);
        return;
      case ".":
      case ">":
        handled();
        stepSpeed(1);
        return;
      case "c":
        handled();
        setCaptionsOn((on) => {
          setStatus(on ? "Captions off" : "Captions on");
          return !on;
        });
        return;
      case "m":
        handled();
        toggleMute();
        return;
      default:
    }
  }, [active, goToChapter, seekBy, stepSpeed, timeline.length, toggle, toggleMute]);

  useEffect(() => {
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [onKeyDown]);

  if (error) {
    return (
      <div className="wt-error" role="alert">
        Could not load the walkthrough: {error}
      </div>
    );
  }
  if (!data) {
    return (
      <div style={{ padding: 40 }} role="status" aria-live="polite">
        Loading walkthrough…
      </div>
    );
  }

  return (
    <div className="wt">
      <a className="wt-skip" href="#wt-player">Skip to player</a>
      <nav className="wt-nav" aria-label="Chapters">
        <h1 className="wt-title">{data.meta.title}</h1>
        <ol>
          {data.chapters.map((ch, i) => (
            <li key={ch.id}>
              <button
                type="button"
                className="wt-chapter"
                aria-current={i === active ? "true" : undefined}
                onClick={() => goToChapter(i)}
              >
                {i + 1}. {ch.title}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <main className="wt-main" id="wt-player">
        <h2 className="wt-sr-only">Player</h2>
        <div className="wt-stage">
          <Player
            ref={ref}
            component={Walkthrough}
            inputProps={{ data }}
            durationInFrames={duration}
            fps={FPS}
            compositionWidth={1920}
            compositionHeight={1080}
            playbackRate={speed}
            // The shell owns the keyboard; the built-in binding also steals
            // focus to the play button every time playback toggles.
            spaceKeyToPlayOrPause={false}
            style={{ width: "100%", maxWidth: 1280, backgroundColor: "#181818" }}
          />
        </div>

        <div className="wt-captions" role="region" aria-label="Captions">
          <p>{caption}</p>
        </div>

        <div className="wt-controls" role="group" aria-label="Playback controls">
          <div className="wt-row">
          <button type="button" onClick={toggle}>{playing ? "Pause" : "Play"}</button>
          <button type="button" onClick={() => goToChapter(active - 1)}>
            Previous chapter
          </button>
          <button type="button" onClick={() => goToChapter(active + 1)}>
            Next chapter
          </button>
          <button type="button" onClick={() => seekBy(-SEEK_SMALL_S)}>
            Back {SEEK_SMALL_S}s
          </button>
          <button type="button" onClick={() => seekBy(SEEK_SMALL_S)}>
            Forward {SEEK_SMALL_S}s
          </button>
          </div>
          <div className="wt-row">
          <input
            className="wt-seek"
            type="range"
            min={0}
            max={duration - 1}
            step={FPS} // one second per arrow press; frame steps are unusable here
            value={frame}
            aria-label="Seek"
            aria-valuetext={`${formatTime(frame, FPS)} of ${formatTime(duration, FPS)}`}
            onChange={(e) => seekTo(Number(e.target.value))}
          />
          <span className="wt-time">
            {formatTime(frame, FPS)} / {formatTime(duration, FPS)}
          </span>
          <label className="wt-time">
            Speed{" "}
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
              {SPEEDS.map((s) => (
                <option key={s} value={s}>{s}×</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            aria-pressed={captionsOn}
            onClick={() => setCaptionsOn((on) => !on)}
          >
            Captions
          </button>
          <button type="button" aria-pressed={muted} onClick={toggleMute}>
            Mute
          </button>
          <button type="button" onClick={() => ref.current?.requestFullscreen()}>
            Fullscreen
          </button>
          </div>
        </div>

        <p className="wt-sr-only" role="status" aria-live="polite">{status}</p>

        <section className="wt-section" aria-labelledby="wt-keys-heading">
          <h2 id="wt-keys-heading">Keyboard shortcuts</h2>
          <ul className="wt-keys">
            <li><kbd>Space</kbd> or <kbd>K</kbd> — play or pause</li>
            <li><kbd>←</kbd> / <kbd>→</kbd> — back or forward {SEEK_SMALL_S} seconds</li>
            <li><kbd>J</kbd> / <kbd>L</kbd> — back or forward {SEEK_LARGE_S} seconds</li>
            <li><kbd>P</kbd> / <kbd>N</kbd> — previous or next chapter</li>
            <li><kbd>Home</kbd> / <kbd>End</kbd> — first or last chapter</li>
            <li><kbd>,</kbd> / <kbd>.</kbd> — slower or faster</li>
            <li><kbd>C</kbd> — captions, <kbd>M</kbd> — mute</li>
          </ul>
        </section>

        <section className="wt-section" aria-labelledby="wt-transcript-heading">
          <h2 id="wt-transcript-heading">Transcript</h2>
          <ol className="wt-transcript">
            {data.chapters.map((ch, i) => (
              <li key={ch.id}>
                <h3>
                  <button
                    type="button"
                    className="wt-jump"
                    aria-current={i === active ? "true" : undefined}
                    onClick={() => goToChapter(i)}
                  >
                    {i + 1}. {ch.title}
                  </button>
                </h3>
                <p>{ch.narration}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
};
