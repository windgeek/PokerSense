"""Desktop server driven by a REAL RealtimePipeline over a REAL captured window.

This is the full loop: QuartzBackend captures mock_table.html (a real macOS
window) -> VisionEngine recognizes it (real OpenCV template matching, the
same calibration proven in run_smoke.py) -> ApplicationOrchestrator/StateEngine
-> Equity -> the same RealtimeAnalysis contract the UI already understands.

Still not a real poker platform (see project notes). This proves the pipeline
plumbing end to end; ui/app.js and poker_engine.desktop.serialize are
completely unaware anything changed.

Usage:
    1. python -m http.server 8944 --directory tools/real_pipeline_smoke
    2. open -a Safari http://localhost:8944/mock_table.html
    3. python tools/real_pipeline_smoke/run_live_server.py
    4. open http://127.0.0.1:8765/ (or run the desktop app pointed at :8765)

Known issue: ``CGWindowListCreateImage`` can intermittently return None for
a window that IS present in the on-screen window list (bounds/on-screen
flags all look correct) -- observed on this dev machine, cause not yet
root-caused (candidates: the window's Space isn't the active Space; some
transient WindowServer state). ``run_smoke.py``'s one-shot capture has been
reliable across many runs; only this long-lived polling loop has hit it.
Treat as a known open issue for the real macOS capture backend, not
something this script papers over.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from poker_engine.confidence.gate import ConfidenceGate  # noqa: E402
from poker_engine.core.enums import PlayerStatus, Position, Street  # noqa: E402
from poker_engine.core.state import PlayerState, PokerState  # noqa: E402
from poker_engine.core.value_objects import ChipAmount  # noqa: E402
from poker_engine.memory.hand_memory import InMemoryHandMemory  # noqa: E402
from poker_engine.orchestrator import ApplicationOrchestrator  # noqa: E402
from poker_engine.perceptual.capture.base import CaptureTarget, Frame  # noqa: E402
from poker_engine.perceptual.capture.quartz_backend import QuartzBackend  # noqa: E402
from poker_engine.realtime.analysis import RealtimeAnalysis  # noqa: E402
from poker_engine.realtime.pipeline import RealtimePipeline  # noqa: E402
from poker_engine.state_engine.engine import StateEngine  # noqa: E402
from vision_setup import WINDOW_TITLE, build  # noqa: E402


def _seed_player(seat: int, hero: bool) -> PlayerState:
    return PlayerState(
        player_id=f"p{seat}",
        seat=seat,
        position=Position.BTN if seat == 0 else Position.SB,
        stack=ChipAmount("100"),
        committed_this_street=ChipAmount("0"),
        committed_this_hand=ChipAmount("0"),
        status=PlayerStatus.ACTIVE,
        has_cards=True,
        is_hero=hero,
        is_dealer=(seat == 0),
    )


def _seed_initial_state() -> PokerState:
    """Empty preflop state -- the pipeline's own recognition drives it from here."""
    return PokerState(
        state_version=0,
        hand_id="live-1",
        street=Street.PREFLOP,
        hero_cards=(),
        board_cards=(),
        players=(_seed_player(0, hero=True), _seed_player(1, hero=False)),
        pot=ChipAmount("0"),
        current_bet=ChipAmount("0"),
        to_call=ChipAmount("0"),
        actor=None,
    )


class QuartzWindowFrameSource:
    """Real FrameSource: captures ``window_title`` fresh on every pull.

    Not the guarded ``realtime.frame_source.MSSFrameSource`` stub (that one
    is deliberately unimplemented to keep real-platform auto-capture out of
    scope). This targets our own mock-table test window, a different,
    explicitly-approved use.
    """

    def __init__(self, backend: QuartzBackend, window_title: str) -> None:
        self._backend = backend
        self._target = CaptureTarget(window_id=window_title)

    def next_frame(self) -> Frame | None:
        return self._backend.capture(self._target)


def _build_pipeline() -> RealtimePipeline:
    backend = QuartzBackend()
    calibration_frame = backend.capture(CaptureTarget(window_id=WINDOW_TITLE))
    table_map, vision = build(calibration_frame)

    orchestrator = ApplicationOrchestrator(
        state_engine=StateEngine(),
        hand_memory=InMemoryHandMemory(),
        confidence_gate=ConfidenceGate(),
    )
    orchestrator.start_hand(_seed_initial_state())
    frame_source = QuartzWindowFrameSource(backend, WINDOW_TITLE)
    return RealtimePipeline(frame_source, vision, table_map, orchestrator)


async def live_analysis_stream(
    interval_seconds: float = 1.0,
) -> AsyncIterator[RealtimeAnalysis]:
    pipeline = _build_pipeline()
    while True:
        step = await asyncio.to_thread(pipeline.step)
        if step is not None:
            yield step.analysis
        await asyncio.sleep(interval_seconds)


def main() -> None:
    import uvicorn

    from poker_engine.desktop.server import create_app

    app = create_app(stream_factory=live_analysis_stream)
    print("Live server (real capture of mock_table.html) on http://127.0.0.1:8765/")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
