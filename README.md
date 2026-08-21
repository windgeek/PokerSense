# PokerSense

[简体中文](README.zh-CN.md) | **English**

PokerSense is a real-time Texas Hold'em training companion for authorized,
self-hosted games. It captures a supported table and displays analysis in a
separate window. The current build recognizes hero cards and reports preflop
equity; the v0.3 target adds explainable action frequencies, sizes, EVs, and
confidence.

PokerSense is not an autoplay bot. It never clicks, types, places bets, or
controls a poker client. The human remains the only executor. The intended
environment is a private table with friends, coaching, and deliberate practice.

## Current support

The current desktop release is calibrated for the hero-card area of a WePoker
H5 heads-up table.

| Feature | Availability |
|---|---|
| macOS and Windows desktop builds | Available from [GitHub Releases](https://github.com/windgeek/PokerSense/releases) |
| Screen capture and live companion window | Available |
| Hero-card recognition for WePoker H5 | Calibrated |
| Equity calculation | Available; preflop hero equity against a random range |
| English and Simplified Chinese UI | Available; preference persists across restarts |
| Board cards, pot and street | Not yet calibrated; shown as unavailable |
| Explainable advice, range tracking, and training feedback | Target architecture; not yet implemented |
| Automated play or client control | Never provided |

When a newly dealt pair of hero cards is confirmed in consecutive frames,
PokerSense starts a new hand automatically. A transient frame during a deal is
not used as a state update.

## Install

Download the latest installer from [GitHub Releases](https://github.com/windgeek/PokerSense/releases):

- macOS: `PokerSense-macos.dmg`
- Windows: `PokerSense-Setup.exe`

macOS asks for Screen Recording permission when capture is first needed. Grant
it to PokerSense in **System Settings → Privacy & Security → Screen Recording**,
then return to the app. The permission is tied to the installed application;
replacing or rebuilding the app can require granting it again.

Windows does not show a Screen Recording permission prompt. PokerSense uses
the local Windows desktop-capture APIs directly.

## Use with WePoker H5

1. Open the WePoker H5 table and keep it visible.
2. Open PokerSense and grant Screen Recording permission if requested.
3. Keep the table on the current macOS Space while PokerSense is reading it.
4. Check the status line in the companion window before relying on a reading.

Only the hero-card area has been measured for this platform. The displayed
equity therefore reflects the recognized hero hand before the flop, against a
random opponent range. It is not a full table-state analysis.

If more than one visible window has the title `WePoker-H5`, PokerSense does not
choose one silently. For development use, list the windows and select an index:

```bash
./.venv/bin/python tools/list_windows.py --title WePoker-H5
make run-desktop ARGS="--window-index 0"
```

On Windows, browser-added title suffixes such as ` - Google Chrome` are
handled automatically; PokerSense matches the stable page title rather than a
specific browser name.

The index follows the current window order. Run the command again after moving,
reopening, or switching windows.

## Privacy

Captured frames are processed in memory and discarded after recognition.
PokerSense does not keep screenshots, video, or a frame history on disk.

The only persisted setting is the interface language:

- macOS: `~/Library/Application Support/PokerSense/settings.json`
- Windows: `%APPDATA%\\PokerSense\\settings.json`

The file contains one of `auto`, `en`, or `zh`. `auto` follows the system
language.

## Development

Python 3.11–3.13 is supported.

```bash
# Install development dependencies
pip install -e ".[dev,desktop,perceptual]"

# Run checks
make test
make lint

# Start the desktop app
make run-desktop

# Start the local server only
make run-desktop-server

# Build a local application bundle
pip install -e ".[dev,desktop,packaging]"
make package
```

The desktop composition lives in `src/poker_engine/desktop/`; the live update
loop is in `src/poker_engine/realtime/`; platform-specific calibration is under
`configs/`.

## Recognition and calibration

PokerSense uses OpenCV template matching and a per-platform layout map. The
WePoker H5 hero-card recognizer is measured against held-out real captures;
details and source calibration data are in:

- [`configs/platform/wepoker__h5_2max.json`](configs/platform/wepoker__h5_2max.json)
- [`configs/vision/wepoker/calibration.json`](configs/vision/wepoker/calibration.json)
- [`docs/vision-engine.md`](docs/vision-engine.md)

Fields without their own calibration are reported as unavailable rather than
guessed.

## Target architecture

![PokerSense v0.3 target architecture](docs/realtime-training-assistant.drawio.svg)

The SVG embeds its draw.io source and can be opened directly in draw.io. The
first result comes from a deterministic local Fast Path. Close decisions and
cache misses may start an asynchronous local resolver, but stale results are
discarded. Critical state uncertainty produces `ABSTAIN`, not a guess.

```text
Authorized table → Capture → Vision → Temporal Consensus → Confidence Gate
  → State/Event Engine v2 → DecisionContext
  → Range + Equity + Strategy Router → Decision Fusion → Advice → Live Coach UI
  → Human action → Hand Memory → Debrief / drills → better priors
```

The canonical design, latency budget, algorithms, contracts, and milestone
exit criteria are in [`architecture.md`](architecture.md).

## Project structure

| Area | Location |
|---|---|
| Domain types and state transitions | `src/poker_engine/core/`, `src/poker_engine/state_engine/` |
| Capture and vision | `src/poker_engine/perceptual/` |
| Equity and real-time pipeline | `src/poker_engine/equity/`, `src/poker_engine/realtime/` |
| Desktop application | `src/poker_engine/desktop/`, `ui/` |
| Tests | `tests/` |
| Platform calibration | `configs/` |

For detailed subsystem notes, see [`docs/`](docs/).

## Roadmap

1. **M1 — trustworthy heads-up state:** calibrate board, pot, stacks, actor,
   and actions; add temporal consensus, betting legality, hand boundaries, and
   chip conservation.
2. **M2 — explainable baseline advice:** add `DecisionContext`, Bayesian combo
   ranges, preflop DB, range equity, action EV, and a measured p95 ≤300 ms Fast
   Path.
3. **M3 — presolved library and training loop:** canonical solution bundles,
   EV-loss debriefs, leak classification, and drills using the live interfaces.
4. **M4 — robust opponent adjustment:** shrink small samples toward population
   priors and bound exploit adjustments with KL regularization.
5. **M5 — asynchronous local resolution:** start with river subgames, enforce
   compute budgets, and discard stale results.

Detailed deliverables and exit criteria are in
[`architecture.md` §9](architecture.md#9-最优实施路线).
