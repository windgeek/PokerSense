# AGENTS.md

Handoff notes for whichever agent picks this up next. Written 2026-08-20 by
Claude after wiring the desktop app to real screen capture (see
`git log -1` on `main`, commit `129e1a0`). Read this before touching
`src/poker_engine/desktop/` or the capture backends.

## Where things stand

The desktop app (`make run-desktop-server`, or
`.claude/launch.json`'s `pokersense-desktop-server` config) runs the real
pipeline end to end: `QuartzBackend` (macOS) captures a named window,
`CornerGlyphCardRecognizer` reads the hero cards, `MeasuredCalibration`
(see `src/poker_engine/perceptual/vision/calibration.py`) gates confidence
based on an actual accuracy measurement instead of an invented number, and
the result streams to the UI over WebSocket. This was tested against a real
captured WePoker screenshot and produced correct hero cards + plausible
equity. Full test suite and flake8 are clean on `main`.

Only **hero cards** are calibrated for WePoker. Board cards, pot, and
street have no measured ROIs yet, so they read `UNKNOWN` and the UI labels
them "not calibrated" — that's expected, not a bug. See
`src/poker_engine/desktop/live.py`'s module docstring for the full scope
statement.

## Environment gotcha: `.venv` and Python version

`pyproject.toml` supports Python 3.11–3.13. This machine only has Python
3.13 (`python3.11`/`3.12` are not installed, no pyenv). To (re)create the
venv on this machine:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev,perceptual,desktop]"
```

**Screen Recording permission is tied to the exact binary path.** Every
time `.venv` is deleted and recreated, macOS treats the new
`.venv/bin/python3` as a different binary identity and screen-capture
calls silently return nothing / an empty window list — no explicit error,
just no data. If `QuartzBackend` suddenly can't see any windows after a
fresh venv, check System Settings → Privacy & Security → Screen Recording
and re-grant it to the new binary before assuming the capture code is
broken.

(Standing project convention: `.venv` gets `rm -rf`'d before every commit
so it never lands in git. That's fine for git hygiene but means the next
agent session on a fresh checkout has to rebuild it — see above.)

## Live capture: two WePoker windows, macOS Spaces

The user runs a 2-max heads-up table locally by opening **two** Chrome
windows with the same title (`WePoker-H5`) — one normal-mode (their own
seat), one incognito-mode (their friend's seat), so they can test with two
accounts on one machine. `QuartzBackend._resolve_window` matches windows
by `kCGWindowName` and **deliberately raises `CaptureError` on ambiguity**
rather than guessing which one to capture (see
`src/poker_engine/perceptual/capture/quartz_backend.py`) — this is
correct behavior, not a bug to route around by picking one arbitrarily.

The user's own window is **the normal-mode Chrome window** (not
incognito). The explicit selection portion is now implemented:

1. **Disambiguation.** `CaptureTarget.window_index` now selects a visible
   same-title match explicitly. `tools/list_windows.py --title WePoker-H5`
   lists index, bounds and owner; pass the chosen value via
   `make run-desktop ARGS="--window-index N"`. Without it, two visible
   matches remain a hard error. The index is current-list-only, so re-list
   after rearranging windows.

2. **macOS Spaces.** `CGWindowListCopyWindowInfo` with
   `kCGWindowListOptionOnScreenOnly` only returns windows on the
   **currently active Space** (virtual desktop). While debugging this
   session, window enumeration flickered between "sees Chrome + everything"
   and "sees only this coding tool's own windows" depending on which Space
   was frontmost at query time. This is a real constraint of the capture
   approach, not a fluke: if the WePoker windows aren't on the active Space
   when the app captures, it will correctly report "not found" — because
   from the OS's perspective, on that Space, it isn't. This needs to be
   either (a) documented as a real usage requirement (keep the poker table
   on the same Space as wherever you're looking at the companion window),
   or (b) worked around by dropping `kCGWindowListOptionOnScreenOnly` and
   instead checking window visibility a different way (accepting
   background-Space windows) — but that changes what "capture" means and
   needs its own accuracy check against real content, not just window
   metadata. I did not resolve this — ran out of turn debugging it live
   with the user before handing off.

## Immediate next step

Get one concrete live repro: user switches to the Space with the normal-mode
WePoker Chrome window, runs `tools/list_windows.py`, then starts the app with
the printed `--window-index` if necessary. Confirm continuous hero-card
recognition while a hand is played. Board/pot/street still require reference
screenshots and calibration.

## Longer-term (from the original roadmap, still valid)

Board/pot/street calibration for WePoker is the next real milestone after
capture is unblocked — needs the user to play a hand to the flop while
someone takes reference screenshots to calibrate ROIs, same process used
for the hero-card calibration in `configs/vision/wepoker/`.
