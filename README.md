# PokerSense

**English** | [简体中文](README.zh-CN.md)

**A real-time Texas Hold'em training assistant for authorized, self-hosted games.** It
watches a poker table (via screen capture), reconstructs a trustworthy game state, and
shows analysis in a live companion window. The current build reports state and equity;
the v0.3 target adds explainable action frequencies, sizes, EVs, and confidence.

It is **not** an autoplay bot: it never clicks, types, places bets, or controls a poker
client. The human remains the only executor. The intended environment is a private table
with friends, coaching, and deliberate practice.

---

## What actually works today

This section is deliberately literal — every claim below has been independently run and
verified on real hardware, not just implemented and assumed correct.

| Capability | Status | Evidence |
|---|---|---|
| Core domain model (immutable value objects, `ChipAmount`/`ChipDelta`, event sourcing) | ✅ Done | 560+ unit tests |
| State Engine (pure-function state machine) | ✅ Done | unit + integration tests |
| Equity Engine (enumeration + Monte Carlo + pot odds + ranges) | ✅ Done | enumeration and Monte Carlo cross-validated to agree at showdown |
| Confidence Gate (low-confidence fields degrade to `UNKNOWN`, never guessed) | ✅ Done | unit tests |
| Screen capture — Windows (`MssBackend`) | ✅ Implemented | unit-tested; not yet run against a real Windows desktop |
| Screen capture — macOS (`QuartzBackend`) | ✅ Implemented and verified | captured a real on-screen window on real hardware |
| Vision recognition (OpenCV template matching) | ✅ Verified against real pixels | see [Real-platform calibration](#real-platform-calibration) below |
| Realtime pipeline (Capture → Vision → State → Equity, one event loop) | ✅ Working | wired and run end to end, driven by a real capture |
| Desktop UI (companion window, live-updating) | ✅ Working | FastAPI + WebSocket backend, HTML/CSS/JS frontend, verified live |
| UI language | ✅ Working | first run follows the system; English/Chinese choices persist across app restarts |
| Desktop app driven by **real screen capture** | ✅ Working against a captured screenshot | recognizes hero cards and computes real equity — no scripted data anywhere in the app |
| Continuous live capture during an active session | ✅ Usable on the active Space | Same-titled windows can be selected explicitly; the table must be on the current macOS Space |
| Packaging (macOS `.dmg`, Windows installer `.exe`, via GitHub Actions) | ✅ Working | CI builds and a tagged release both succeeded |
| Hero-card recognition on a real platform (WePoker H5) | ✅ Calibrated and measured | 48/48 on held-out real captures — see [Real-platform calibration](#real-platform-calibration) |
| Board cards / pot / street on a real platform | ❌ Not done | only the hero-card region has been calibrated so far |
| Explainable advice / range tracking / strategy routing / training feedback | 🧭 Target architecture | contracts and implementation order are defined in [v0.3 architecture](architecture.md) |

### Confidence is earned, not chosen

A recognizer that scores 62/62 has *not* demonstrated 100% accuracy — with that sample
size the 95% confidence lower bound is about 95.8%, and claiming more would be inventing
evidence. So the confidence a field reports is derived from its recorded measurement
rather than picked by hand:
[`configs/vision/wepoker/calibration.json`](configs/vision/wepoker/calibration.json)
stores the sample count, the correct count, and the raw-score gap separating readable
cards from non-cards (observed: non-cards scored ≤0.335, real cards ≥0.664).
`MeasuredCalibration` turns that into both the calibrated confidence and the abstain
floor, and the confidence gate's threshold is set to the same figure.

The practical consequence: **collecting more verified samples is what raises the
threshold**, and a field nobody has measured (board, pot, street) gets a threshold of
1.0 — unreachable — so it stays `UNKNOWN` instead of borrowing the hero-card
measurement's credibility.

### Real-platform calibration

Calibrated against a live **WePoker H5** table: real screen captures via
`QuartzBackend`, hero-card ROIs measured from those captures
(`configs/platform/wepoker__h5_2max.json`), and rank/suit templates cut from real card
art (`configs/vision/wepoker/`).

Measured on 62 real card captures with verified ground truth, then re-measured with
every template-source image excluded:

| Metric | Whole-card matching | Corner-glyph matching |
|---|---|---|
| Rank | 98.1% | **100%** |
| Suit — red (♥♦) | 95.7% | **100%** |
| Suit — black (♣♠) | 48.3% | **100%** |
| Full card | 67.3% | **100%** |

Held-out result: **48/48** (25 distinct cards, 30 of them black-suited).

The 48% black-suit score was not noise — clubs and spades collapsed into each other
almost one-directionally. Two concrete causes, both found by inspecting the actual
pixels rather than tuning thresholds:

1. Slicing the card corner at a fixed offset cut into the bottom of the rank glyph and
   truncated the suit glyph, so every template carried a fragment of an unrelated digit.
2. The large centre pip bleeds into the same x-range as the corner index, which made the
   club template wider than the spade template; `matchTemplate` then rescaled one to the
   other's aspect ratio, destroying the shape difference it was supposed to measure.

[`corner_glyph_recognizer.py`](src/poker_engine/perceptual/vision/corner_glyph_recognizer.py)
fixes both by locating glyphs with connected components instead of fixed offsets,
rejecting table felt by colour, and letterboxing every glyph onto a fixed grid before
matching. It's a separate `CardRecognizer` Protocol implementation, so it plugs in
without touching the sealed template matcher.

Regression tests run against committed real-capture fixtures
(`tests/vision/fixtures/wepoker/`), all of them held-out samples.

### macOS Spaces and same-titled windows

`QuartzBackend` captures only visible, unminimized windows on the **current macOS
Space**. Put the WePoker table on that Space before starting the companion app; the UI
will tell you to switch Spaces if it cannot see the table.

When two visible windows have the same title, PokerSense still refuses to guess. List
them, then pass the index for your table explicitly:

```bash
./.venv/bin/python tools/list_windows.py --title WePoker-H5
make run-desktop-server ARGS="--window-index 0"
# or: make run-desktop ARGS="--window-index 0"
```

The index is the current window-list order, not a persistent ID. Re-run the command
after rearranging windows, switching Spaces, or reopening Chrome.

### Privacy and local storage

PokerSense processes screen frames **in memory only**. It does not write captured
frames, screenshots, or a frame history to disk; each frame is recognized and then
discarded. The only user preference currently stored is the selected UI language:

- macOS: `~/Library/Application Support/PokerSense/settings.json`
- Windows: `%APPDATA%\\PokerSense\\settings.json`

The file is a small JSON preference (`auto`, `en`, or `zh`) and is atomically replaced
rather than appended to. On first run, `auto` follows the operating system language.

---

## Architecture

![PokerSense v0.3 target architecture](docs/realtime-training-assistant.drawio.svg)

The SVG embeds its draw.io source and can be opened directly in draw.io for editing.
Solid foundations on the left/top are already partially implemented; the strategy,
decision-fusion, and training-loop modules are the staged v0.3 target.

**Design principle, in priority order: correctness > stability > observability >
performance > feature count.** Concretely: money is always `decimal.Decimal`, never
`float`; every state object is deep-immutable; a field the Vision Engine isn't confident
about becomes `UNKNOWN`, never a guess; every recognizer's occupancy/identity evidence is
independently derived and reconciled, not conflated.

See [`architecture.md`](architecture.md) for the canonical design: data contracts,
latency budget, range and EV algorithms, Fast/Slow strategy routing, abstention rules,
and the milestone exit criteria.

### Data flow, end to end

```text
Authorized table → Capture → Vision → Temporal Consensus → Confidence Gate
  → State/Event Engine v2 → DecisionContext
  → Range + Equity + Strategy Router → Decision Fusion → Advice → Live Coach UI
  → Human action → Hand Memory → Debrief / drills → better priors for later hands
```

The first result comes from a deterministic local Fast Path. Cache misses and close
decisions may start an asynchronous local resolver; a result is accepted only when its
`hand_id` and `state_version` still match. Any critical state uncertainty produces
`ABSTAIN`, not a guessed recommendation.

---

## Module map

| Module | Path | What it owns |
|---|---|---|
| Core | `src/poker_engine/core/` | Immutable domain types: `PokerState`, `Card`, `ChipAmount`/`ChipDelta`, events. Zero third-party runtime dependencies. |
| State Engine | `src/poker_engine/state_engine/` | Pure-function state transitions; rejects illegal/regressive state. |
| Hand Memory | `src/poker_engine/memory/` | Append-only event store; a hand can be fully replayed from it. |
| Confidence | `src/poker_engine/confidence/` | Gates low-confidence fields to `UNKNOWN` before they can drive a decision. |
| Orchestrator | `src/poker_engine/orchestrator/` | Central scheduler; the only module that calls into State + Hand Memory together. Contains no algorithms. |
| Perceptual — Capture | `src/poker_engine/perceptual/capture/` | `FakeBackend` (tests), `MssBackend` (Windows), `QuartzBackend` (macOS) — all implement the same `CaptureService` interface. |
| Perceptual — Vision | `src/poker_engine/perceptual/vision/` | Card/street/pot recognizers (OpenCV template matching), ROI mapping, per-detector confidence calibration. |
| Equity | `src/poker_engine/equity/` | Hand evaluator, enumeration, Monte Carlo, pot odds, range equity. |
| Realtime | `src/poker_engine/realtime/` | The event loop tying capture → vision → state → equity together, with change detection so idle frames don't trigger recompute. |
| Desktop | `src/poker_engine/desktop/` | `live.py` assembles the live-capture pipeline from committed calibration; `server.py` serves the UI and streams `RealtimeAnalysis` over WebSocket; `app.py` opens it in a `pywebview` native window. |
| UI | `ui/` | The companion window itself — plain HTML/CSS/JS, no build step, no external dependencies. |

Deeper design docs live in [`docs/`](docs/): `core-contracts.md`, `state-engine.md`,
`vision-engine.md`, `confidence-gate.md`, `hand-memory.md`, `orchestrator.md`,
`capture-and-table-mapping.md`, `serialization.md`, `tech-stack-matrix.md`, plus
architecture decision records in [`docs/adr/`](docs/adr/).

---

## How recognition actually works today (and an open question)

Recognition in `src/poker_engine/perceptual/vision/` is three layers, and it's important
to be precise about which parts generalize across poker platforms and which don't.

1. **Where things are — `TableMap` / ROI.** A per-platform JSON config of normalized
   (0–1) rectangles: where the hero cards are on screen, where the board is, where the
   pot text is. Normalized so it survives resolution changes on the *same* platform. This
   config is calibrated once, by hand, per platform+layout — there's no way around that;
   every poker client lays out its table differently.
2. **Whether a slot has a card — `TemplateBoardSlotDetector`.** Pure pixel statistics
   (brightness × edge-texture density), no knowledge of *which* card. This part is
   already platform-agnostic — a bright, textured region reads as "occupied" regardless
   of art style.
3. **Which card it is — `CornerGlyphCardRecognizer`.** Isolates the card's corner index
   (rank above, suit below) and matches each glyph against 13 rank and 4 suit templates.
   **This is the part that's actually platform-specific** — the templates are pixel crops
   taken from one specific platform's card art, and the corner window is that platform's
   geometry. A different card skin means new templates (about 17 crops), though the
   recognizer code is unchanged. It is that sensitive to exact pixel content: a
   loosely-cropped template scored 0.16 against 0.97 for a tight crop of the *same*
   glyph.

So: layout detection and occupancy detection are already general-purpose; card identity
is not — it's bound to whatever screenshots the templates were cut from.

The current decision is **calibrate per platform**, starting with WePoker (done for hero
cards — see [Real-platform calibration](#real-platform-calibration)). Adding a platform
means capturing its table, measuring ROIs, and cutting ~17 glyph templates from its card
art; the recognizer code itself is unchanged.

**The longer-term open question** is whether recognition should generalize to arbitrary
platforms with no calibration at all. The realistic way there is a vision-language model
(VLM) — prompt a multimodal model with the frame and ask what the cards/pot are, instead
of pixel-matching. That generalizes across skins with no calibration step, at the cost of
latency (hundreds of ms to seconds vs. ~12ms today), a per-call cost, a network
dependency, and less deterministic output. The architecture already reserves a slot for
exactly this: the Fast/Slow path split (`architecture.md` §4) was designed for
"cache/deterministic path now, LLM/Solver path later" — a VLM recognizer is a natural
Slow Path candidate, not a rewrite of the Fast Path.

---

## Quick start

Python 3.11–3.13 is supported. Use the project's `.venv` where possible: macOS Screen
Recording permission is tied to the executable path, so recreating the environment may
require granting permission again.

```bash
# Core engine + tests
pip install -e ".[dev]"
make test
make lint

# Screen capture (adds mss on Windows, pyobjc/Quartz on macOS)
pip install -e ".[dev,perceptual]"

# Desktop app (adds FastAPI, uvicorn, pywebview)
pip install -e ".[dev,desktop]"
make run-desktop           # native companion window, reading a live table
make run-desktop-server    # server only, open http://127.0.0.1:8765 in a browser

# Package into a standalone app (adds PyInstaller)
pip install -e ".[dev,desktop,packaging]"
make package                # -> dist/PokerSense.app (macOS) or dist/PokerSense/ (Windows)
```

The desktop app runs the real pipeline: it captures the poker window, recognizes the
hero cards, and computes equity for the recognized hand. There is no scripted demo data
in it. If the window is not open, or screen-recording permission has not been granted,
the app says so rather than showing anything invented.

What it does *not* show yet is board cards, pot or street: those have no measured ROIs
for WePoker, so they read `UNKNOWN` and the app labels them "not calibrated". The equity
displayed is therefore preflop equity for the hero hand against a random range — a real
number, but not a full table read.

CI (`.github/workflows/ci.yml`) runs the full test suite + lint on both macOS and Windows
on every push. `.github/workflows/build-desktop.yml` builds a proper installer for each
platform — a `.dmg` on macOS (signed + notarized if the Apple Developer secrets are
configured, unsigned otherwise) and a `PokerSense-Setup.exe` on Windows (via Inno Setup)
— and attaches both to a GitHub Release on a version tag (`git tag v0.1.0 && git push
origin v0.1.0`).

---

## Roadmap

The shortest route to useful, reliable advice is:

1. **M1 — trustworthy heads-up state:** calibrate board, pot, stacks, actor, and actions;
   add temporal consensus, betting legality, hand boundaries, and chip conservation.
2. **M2 — explainable baseline advice:** add `DecisionContext`, Bayesian combo ranges,
   preflop DB, range equity, action EV, `Advice`, and a measured p95 ≤300 ms Fast Path.
3. **M3 — presolved library and training loop:** canonical solution bundles, EV-loss
   debriefs, leak classification, and drills using the same interfaces as live advice.
4. **M4 — robust opponent adjustment:** shrink small samples toward population priors and
   use KL-regularized exploit adjustments with a bounded worst-case loss.
5. **M5 — asynchronous local resolution:** start with river subgames; enforce compute
   budgets and discard stale results. Slow results never block first advice.

Detailed deliverables and exit criteria are in
[`architecture.md` §9](architecture.md#9-最优实施路线).

---

## Project conventions

- Money is always `decimal.Decimal` via `ChipAmount` (non-negative) / `ChipDelta`
  (signed) — never `float`.
- Timestamps are always timezone-aware `datetime`; no falsy-fallback patterns.
- Core domain objects are deep-immutable (`tuple`, `frozenset`, `MappingProxyType`, no
  mutable containers leak out).
- A field the Vision Engine can't confidently read becomes `UNKNOWN`, not a guess — it's
  better to show nothing than to show something wrong.
- No AI-agent process ceremony (task plans, self-check reports, versioned result
  snapshots) lives in this repo — git history is the source of truth for what changed and
  why; commit messages carry that context.
