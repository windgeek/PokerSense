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
- The desktop app reads a live WePoker H5 window, recognizes **hero cards**,
  and displays preflop equity against a random range.
- A different hero-card pair must be visible for two consecutive frames before
  it starts a new hand. This prevents deal-animation reads from replacing the
  prior hand while allowing the companion window to refresh on every deal.
- Board cards, pot, and street are deliberately unavailable until each has
  its own measured platform calibration. Do not infer them from hero-card
  confidence.
- Capture frames are memory-only. The only persistent user setting is UI
  language (`auto`, `en`, or `zh`).

## Live-capture constraints

- The user tests a two-player WePoker table in two Chrome windows with the
  same title, `WePoker-H5`: the normal Chrome window is the user's seat and
  the incognito window is the second seat.
- Never choose a same-titled window implicitly. Use
  `tools/list_windows.py --title WePoker-H5` and pass an explicit
  `--window-index` when both are visible.
- macOS capture sees windows only on the active Space. Keep the poker table
  on the current Space while using PokerSense.
- Screen Recording permission is tied to the executable path. A rebuilt venv
  or a newly installed app may need permission granted again in **System
  Settings → Privacy & Security → Screen Recording**.

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

1. Collect user-labeled real captures, especially genuine recognition errors,
   deal transitions, and result overlays, before changing hero-card templates
   or thresholds.
2. Calibrate board cards, pot, and street from independently measured real
   table captures.
3. Improve CI coverage so ordinary feature-branch pushes and pull requests run
   the test suite, not only `main` and release tags.
