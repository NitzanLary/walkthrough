# Player accessibility

The `walkthrough view` page (`src/Player.tsx`) is operable without a mouse and
without sight of the screen. This file records what is guaranteed and how to
re-check it by hand — the automated checks cover structure, not experience.

## What the player provides

- Chapter navigation is a `<nav>` of `<button>`s in an ordered list; the chapter
  under the playhead carries `aria-current="true"` (and is bold and outlined, so
  the state is not colour alone).
- Every playback action has a control *and* a shortcut: play/pause, ±5s, ±10s,
  previous/next chapter, first/last chapter, speed, captions, mute, fullscreen.
  Shortcuts are listed on the page itself under "Keyboard shortcuts".
- Captions are on by default, derived from each chapter's narration text and
  timed against its audio duration. The full transcript sits below the player,
  with every chapter title as a button that seeks to it.
- A visible focus ring (`:focus-visible`, 3px) is defined for all controls, and
  a "Skip to player" link precedes the chapter list.
- Loading, load failure, and playback state changes are announced through a
  polite `role="status"` region; a failure to load renders `role="alert"`.
- Under `prefers-reduced-motion: reduce` the camera cuts to each chapter's
  framing instead of panning and zooming into it. Framing is unchanged.
- Below 800px the chapter list stacks above the player. Nothing is hidden and
  the transcript stays in the flow.

## Automated checks

```bash
cd renderer && npx vitest run
```

- `src/__tests__/Player.a11y.test.tsx` runs `axe-core` (WCAG 2.0/2.1 A and AA)
  over the player shell, and drives chapter navigation and every shortcut from
  the keyboard.
- `src/components/__tests__/Camera.test.tsx` pins the reduced-motion camera:
  the rendered transform equals the chapter's target framing at every frame.
- `src/lib/__tests__/captions.test.ts` pins cue timing against the chapter audio.

jsdom cannot evaluate colour contrast, so that rule reports as *incomplete*
there. To check it for real, serve the player (`walkthrough view`) and run axe
in the browser console:

```js
const s = document.createElement("script");
s.src = "https://unpkg.com/axe-core/axe.min.js";
s.onload = () => axe.run(document, {
  runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
}).then((r) => console.log(r.violations, r.incomplete.map((i) => i.id)));
document.head.appendChild(s);
```

## Keyboard-only test

Serve the player, then put the mouse away.

1. `Tab` from the top. First stop is "Skip to player"; press `Enter` and focus
   moves past the chapter list. Every stop shows a visible ring.
2. `Tab` through to the chapter list and press `Enter` on chapter 3. The
   playhead jumps there, that entry becomes the current one, and the status
   region announces "Chapter 3 of 6: …".
3. Press `Space` with nothing focused — playback starts. Press `Space` again
   with the "Play" button focused — it toggles once, not twice.
4. `→` / `←` move 5 seconds, `L` / `J` move 10, `N` / `P` change chapter,
   `Home` / `End` go to the first and last chapter.
5. `.` and `,` step the speed; the Speed menu follows. `C` toggles captions;
   `M` toggles mute.
6. Focus the Seek slider and press `←`/`→`: it moves a second at a time, and
   the ±5s shortcut does not also fire.

## Screen-reader smoke test

VoiceOver (`Cmd-F5`), NVDA, or Orca. Read the page top to bottom:

1. The chapter list is announced as a navigation landmark named "Chapters" with
   6 items; the playing chapter is announced as "current".
2. Activating a chapter announces "Chapter *n* of 6: *title*" from the status
   region — without moving focus.
3. Play/pause announces "Playing" / "Paused". Speed and caption changes announce
   their new state.
4. The transcript is reachable as a list of chapter headings with the full
   narration under each, so the whole walkthrough can be read without playing it.
5. Nothing double-speaks: the caption bar is a labelled region, not a live one,
   because the narration audio already carries that text.

## Known gap

Cues are split from the narration text and timed by character share, not by the
provider's word alignment: `narrate` caches clips by text and the cache keeps
only the audio and its duration, so a cached chapter has no `.words.json` to
read. Word-accurate cues need the alignment carried through the cache first.
