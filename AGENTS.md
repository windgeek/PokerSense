# AGENTS.md

Project operating notes for contributors and coding agents. Read this before
changing desktop capture, recognition, packaging, or project documentation.

## Working agreement

1. Inspect the working tree and this file before changing code. Preserve any
   unrelated local changes.
2. Verify every code change in proportion to its risk. A user-facing desktop
   change requires focused tests; a release also requires a local package
   check before GitHub packaging.
3. At the end of every material task, update this file's **Current state** or
   **Progress log**. Record the outcome, affected version/commit when relevant,
   verification performed, and any remaining limitation. Do not add routine
   narration or duplicate git history.
4. Keep documentation aligned with the product:
   - Update `README.md` and `README.zh-CN.md` when installation, supported
     behavior, privacy, or user-visible limitations change.
   - Update the relevant file in `docs/` when a contract, architecture, or
     subsystem behavior changes.
   - Update release/version files together: `pyproject.toml`,
     `src/poker_engine/__init__.py`, `packaging/pokersense.spec`, and
     `packaging/pokersense.iss`.
5. Remove a Markdown document only after confirming it is obsolete or fully
   duplicated, checking references with `rg`, and moving any still-useful
   information into its replacement. An unlinked design document is not, by
   itself, evidence that it is disposable.

## Current state

- Default branch: `main`.
- Current release: `v0.1.11` — [GitHub Release](https://github.com/windgeek/PokerSense/releases/tag/v0.1.11), source commit `f963181`.
- The `main` desktop path reads WePoker Android from a portrait LDPlayer
  instance over ADB, recognizes **hero cards**, and displays preflop equity
  against a random range. Published v0.1.11 installers still contain the
  legacy H5 path; do not describe Android capture as released yet.
- A different hero-card pair must be visible for two consecutive frames before
  it starts a new hand. This prevents deal-animation reads from replacing the
  prior hand while allowing the companion window to refresh on every deal.
- Android board cards, pot, seats/stacks, dealer/actor, actions, and street are
  deliberately unavailable until each has
  its own measured platform calibration. Do not infer them from hero-card
  confidence.
- Capture frames are memory-only. The only persistent user setting is UI
  language (`auto`, `en`, or `zh`).

## Live-capture constraints

- Production input is `adb -s <serial> exec-out screencap -p` from LDPlayer,
  currently calibrated at 1440x2560 portrait. Host window coordinates, DPI,
  visibility, and occlusion are not part of the Android TableMap.
- Never choose among multiple ADB devices implicitly. `auto` is allowed only
  when exactly one authorized device exists; otherwise require
  `--device-serial` or `POKERSENSE_ADB_SERIAL`.
- Resolve ADB from `POKERSENSE_ADB_PATH` or PATH. Treat offline, unauthorized,
  timeout, corrupt PNG, and device disappearance as recoverable capture errors.
- Android and H5 never share ROIs or calibration evidence. They may share
  platform-neutral recognition algorithms and identical card-art templates.
- Real calibration screenshots and ZIPs are private inputs, ignored by Git,
  and never packaged. Retain only a small redacted labeled regression set.

## Local development and packaging

Python 3.11–3.13 is supported. On this machine Python 3.13 is used:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev,perceptual,desktop,packaging]"

./.venv/bin/python -m pytest -q
./.venv/bin/python -m flake8 src tests
./.venv/bin/pyinstaller packaging/pokersense.spec \
  --distpath dist --workpath build --noconfirm
```

For a macOS build, verify the bundle version and signature structure:

```bash
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' \
  dist/PokerSense.app/Contents/Info.plist
codesign --verify --deep --strict --verbose=2 dist/PokerSense.app
```

The user validates GitHub release installers. Local verification should cover
tests, lint, package construction, bundle version, and code-signature
structure; do not represent a local build as a clean-user installation test.

## Documentation map

- `README.md` and `README.zh-CN.md`: product scope, installation, privacy,
  usage, and release-facing limitations.
- `architecture.md`: overall design and data flow.
- `docs/`: subsystem contracts and architecture decisions. Keep these files
  concise and update the owning document rather than creating duplicate notes.
- `configs/vision/wepoker/` and `configs/platform/`: measured recognition
  calibration, not marketing claims. Update calibration evidence together with
  recognizer changes.

## Progress log

- **2026-08-23 — 234-frame Android dataset audit:** inspected the private
  LDPlayer ZIP without adding its contents to the workspace or Git. It contains
  234 valid 1440x2560 PNGs plus 234 sidecars: the original 178-frame sequence
  and 56 later `before-2` / `before-1` / `action` captures, not 234 independent
  new samples. All prior 66 deduplicated frames are present exactly. The
  current Android hero recognizer produced 188 `VALID`, 39 `UNKNOWN`, and seven
  low-score duplicate-card `CONFLICT` outcomes; reviewed action frames show
  the conflicts are card backs and the low-score candidates are overlays or
  correctly abstained visible hands. No confirmed false `VALID` was found in
  the reviewed set, but the sidecars still lack hero/board/street/action ground
  truth, so calibration counts and thresholds were deliberately unchanged.
  The new temporal triplets materially improve coverage for deal transitions,
  folds, results, menus, multiplayer/showdown geometry, and negative scenes.
  No product code changed for this audit.

- **2026-08-23 — Android/LDPlayer production pivot:** replaced the default H5
  window path on `main` with explicit ADB device capture for WePoker Android
  portrait frames. Added fail-closed multi-device selection, timeout/error/PNG
  validation, a 1440x2560 Android TableMap, Android-specific hero geometry and
  calibration, and kept shared WePoker card-art templates separate from ROI
  evidence. On 66 private deduplicated frames from two LDPlayer instances,
  the production VisionEngine read all 58 visible-hand frames correctly across
  23 distinct hero hands (minimum accepted raw score 0.771); all eight
  login/transition/menu/no-card frames abstained. Raw frames remain untracked
  and are not runtime assets. Focused and full tests (690 passed, 3 skipped),
  flake8, legacy-H5 calibration loading, and package-resource inclusion checks
  passed; live Windows LDPlayer and package verification remain pending.

- **2026-08-22 — experimental board calibration:** calibrated a read-only
  normalized board search band and dynamic card-face geometry on three of the
  13 unique supplied WePoker screenshots (one flop, one river, one empty
  board), then evaluated the frozen rules on the remaining ten. Reusing the
  existing held-out corner-glyph templates, the experiment read every stable
  board exactly and abstained on both the vertically occluded turn and the
  one-card deal animation: 13/13 overall scene outcomes and 10/10 on the
  holdout, averaging 2.663ms (p95 4.180ms). This is promising calibration
  evidence, not production support: the sample comes from one table/client
  family, static empty-board detection still needs temporal/street context,
  and the current fixed five-slot `BoardSlotLayout` cannot express the
  observed dynamically centered flop/turn/river geometry. No runtime,
  configuration, API secret, or supplied frame was persisted.
- **2026-08-21 — DeepSeek V4 Flash Vision experiment:** benchmarked the
  official `deepseek-v4-flash-vision-exp` API against 14 supplied WePoker
  screenshots (13 unique), without changing runtime code or retaining frames.
  Full-screen VLM input read the hero hand correctly on 10/13 unique images
  and all visible hero+board cards on 5/13 after normalizing `10` to `T`; it
  frequently confused suits and incorrectly accepted a mid-deal frame as a
  stable flop. Adding explicit hero and board crops corrected 5 of the 8
  retested failures, but the occluded turn, deal animation, and one showdown
  suit remained wrong. Full-screen calls averaged 3.188s (p95 3.893s); 14
  calls used 8,218 input and 2,517 output tokens, costing about $0.00347
  off-peak or $0.00694 peak at the published rates. The existing local hero
  recognizer averaged 4.49ms and produced 10/13 exact `VALID` reads plus three
  `UNKNOWN` abstentions, with no incorrect accepted hand. Conclusion: do not
  replace trusted local/temporal perception with full-screen VLM inference;
  evaluate an event-triggered, ROI-cropped VLM adapter behind deterministic
  scene, temporal, schema, and card-consistency gates.
- **2026-08-21 — v0.3 target architecture:** replaced the frozen v0.2.1
  plan with a staged architecture for authorized, self-hosted training. The
  design adds trusted temporal perception, State/Event Engine v2, Bayesian
  range tracking, Fast/Slow strategy routing, Decision Fusion, abstention,
  and a live-to-debrief training loop. English and Chinese product docs now
  distinguish current capabilities from the M1–M5 target. The embedded-source
  draw.io SVG passed XML validation, draw.io reopen/export, and visual review;
  the full test suite and flake8 passed. Documentation only; no runtime or
  release artifact changed.
- **2026-08-21 — v0.1.11:** a real Windows retest showed
  Chrome exposes the table as `WePoker-H5 - Google Chrome`, while the Windows
  backend still required an exact `WePoker-H5` title. Windows matching now
  normalizes titles, accepts generic host suffixes only at explicit separator
  boundaries, supports `window_index`, and honors the existing opt-in primary
  display fallback for the full-screen WePoker calibration. It does not bind
  behavior to a Chrome-specific suffix or use arbitrary substring matching.
  Focused and full local tests, flake8, local packaging checks, macOS/Windows
  CI, both installer builds, and GitHub release upload passed. Source commit
  `f963181`; clean-user Windows retest remains pending.
- **2026-08-21 — v0.1.10:** after v0.1.9 fixed startup,
  a real Windows run exposed the next blocker: the WebView host had already
  established a non-Per-Monitor process DPI mode. `MssBackend` now uses
  Windows mixed-mode DPI and establishes Per-Monitor V2 on every capture
  worker thread before reading physical-pixel coordinates. Focused and full
  local tests, flake8, the local package checks, macOS/Windows CI (including
  Win32-specific DPI tests), both installer builds, and GitHub release upload
  passed. Source commit `94bdc47`; clean-user Windows retest remains pending.
- **2026-08-21 — v0.1.9:** fixed the Windows packaged
  app's missing `mss` dependency, wait for the local uvicorn server before
  opening the webview, and convert capture initialization/runtime failures to
  recoverable UI errors instead of closing the WebSocket. Added focused
  regression tests and a Windows workflow dependency check. Full tests and
  flake8 passed locally and on macOS/Windows CI; the local macOS bundle passed
  version, resource, signature-structure, and HTTP startup checks; both GitHub
  installers built and were published. Source commit `91de955`.
- **2026-08-21 — Windows v0.1.8 startup diagnosis:** the release workflow
  installs `.[desktop,packaging]` but omits the `perceptual` extra that provides
  `mss`.  The frozen Windows app can therefore serve its UI, but opening `/ws`
  raises an uncaught `RuntimeError` while constructing `MssBackend`; the UI
  reports a disconnect and reconnects indefinitely.  The first-launch
  `ERR_CONNECTION_REFUSED` is a separate server-readiness race because the
  webview navigates immediately after starting the server thread.  Windows has
  no macOS-style Screen Recording permission prompt.  Diagnosis was verified
  by tracing the packaging, desktop startup, WebSocket, and capture code paths;
  no product code or release artifact was changed.
- **2026-08-20 — v0.1.8:** fixed stale hero cards across hands. After two
  matching frames show a different pair, the live pipeline closes the active
  capture hand and starts a fresh hand. Regression coverage added; full test
  suite, flake8, local macOS bundle validation, and GitHub macOS/Windows
  release builds passed. Commit `e827f62` is on `main`.
- **2026-08-20 — documentation maintenance:** rewrote English and Simplified
  Chinese READMEs as concise product documentation; audited Markdown files.
  Existing design documents remain in scope and were retained.

## Open work

1. Run the new ADB path against a live Windows LDPlayer instance, measure
   capture latency/reconnect behavior, and package it only after that passes.
2. Collect user-labeled Android captures for board, pot, occupied/active seats,
   stacks, dealer/actor, actions, action history, all-in/side-pot, hand
   transitions, overlays, and genuine failures.
3. Calibrate Android board cards, pot, and street from independently measured
   real table captures; keep every unmeasured field `UNKNOWN`.
4. Improve CI coverage so ordinary feature-branch pushes and pull requests run
   the test suite, not only `main` and release tags.
