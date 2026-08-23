"""Live capture from WePoker Android running in LDPlayer.

Assembles the whole chain the engine was built for —

    ADB CaptureService -> VisionEngine -> ChangeDetector -> Orchestrator
        -> StateEngine -> Equity -> RealtimeAnalysis

— against the emulator's raw portrait framebuffer, using calibration measured
from real 1440x2560 LDPlayer ADB captures.

Scope, stated plainly: only the **hero cards** are calibrated for Android so
far. Board cards, pot and street have no measured ROIs yet, so the Vision
Engine reports them ``UNKNOWN`` and the equity shown is preflop equity for
the hero hand against a random range. That is a real, useful number, but it
is not a full table read — finishing the calibration is what closes that gap.

Recoverable problems (ADB unavailable, emulator stopped, ambiguous devices,
or a resolution outside the calibrated aspect tolerance) are surfaced as
:class:`LiveCaptureError` so the UI can show what is wrong instead of the
process dying.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import cv2

from poker_engine.confidence.gate import ConfidenceGate
from poker_engine.core.enums import ActionType, PlayerStatus, Position, Street
from poker_engine.core.state import PlayerState, PokerState
from poker_engine.core.value_objects import ChipAmount
from poker_engine.memory.hand_memory import InMemoryHandMemory
from poker_engine.orchestrator import ApplicationOrchestrator
from poker_engine.perceptual.capture.base import (
    CaptureError,
    CaptureService,
    CaptureTarget,
    Frame,
)
from poker_engine.perceptual.vision.action_recognizer import (
    ActionTemplateSet,
    TemplateActionRecognizer,
)
from poker_engine.perceptual.vision.amount_recognizer import (
    DigitTemplateSet,
    TemplateAmountRecognizer,
)
from poker_engine.perceptual.vision.asset_manifest import VisionAssetManifest
from poker_engine.perceptual.vision.board_slot_detector import (
    TemplateBoardSlotDetector,
)
from poker_engine.perceptual.vision.calibration import (
    CalibrationBins,
    ConfidenceCalibrator,
    MeasuredCalibration,
)
from poker_engine.perceptual.vision.card_layout import (
    BoardSlotLayout,
    CardSubROI,
    hero_layout_from_dict,
)
from poker_engine.perceptual.vision.corner_glyph_recognizer import (
    CornerGlyphCardRecognizer,
    CornerGlyphTemplateSet,
)
from poker_engine.perceptual.vision.engine import VisionEngine
from poker_engine.perceptual.vision.errors import TableMapError
from poker_engine.perceptual.vision.street_detector import TemplateStreetDetector
from poker_engine.perceptual.vision.table_map import TableMap
from poker_engine.realtime.pipeline import RealtimePipeline
from poker_engine.state_engine.engine import StateEngine
from poker_engine.strategy.contracts import GameConfig, GameType
from poker_engine.strategy.orchestration import StrategyOrchestrator
from poker_engine.strategy.router import StrategyRouter

from .errors import LiveCaptureError
from .serialize import DesktopFrame
from .strategy_live import LiveStrategySession


def _resource_root() -> Path:
    """Return the checkout root or PyInstaller's bundled resource directory."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base)
    return Path(__file__).resolve().parents[3]


_REPO_ROOT = _resource_root()
DEFAULT_PLATFORM = "wepoker_android"
DEFAULT_LAYOUT = "ldplayer_portrait_1440x2560"
DEFAULT_DEVICE_SERIAL = os.environ.get("POKERSENSE_ADB_SERIAL", "auto")


def build_capture_backend() -> CaptureService:
    """Return the production ADB backend."""
    from poker_engine.perceptual.capture.adb_backend import AdbBackend

    try:
        return AdbBackend()
    except RuntimeError as exc:
        raise LiveCaptureError(str(exc)) from exc


def _uncalibrated(name: str) -> ConfidenceCalibrator:
    """A calibrator for a field nothing has been measured about.

    It reports zero confidence at every raw score, so the field is always
    gated to UNKNOWN. This is deliberate: an uncalibrated field must not
    inherit a calibrated field's confidence just because they share a frame.
    """
    return ConfidenceCalibrator(
        name=name,
        version=1,
        bins=CalibrationBins(edges=(0.0, 1.0), confidence=(0.0,)),
        abstain_floor=1.0,
    )


def load_measured_calibration(vision_dir: Path) -> MeasuredCalibration:
    """Load the committed accuracy measurement for a platform's cards."""
    path = vision_dir / "calibration.json"
    if not path.is_file():
        raise LiveCaptureError(f"no calibration measurement at {path}")
    data = json.loads(path.read_text())["card"]
    return MeasuredCalibration(
        samples=data["samples"],
        correct=data["correct"],
        readable_score_floor=data["readable_score_floor"],
        unreadable_score_ceiling=data["unreadable_score_ceiling"],
        source=data["source"],
    )


def build_confidence_gate(measured: MeasuredCalibration) -> ConfidenceGate:
    """Gate thresholds set to what the measurement actually supports.

    The threshold is not a wish about how good recognition ought to be; it
    is the accuracy the evidence demonstrates. Collecting more samples
    raises what can be claimed, and the threshold rises with it — see
    ``configs/vision/<platform>/calibration.json``.

    Fields with no measurement keep a threshold of 1.0, which nothing can
    clear, so they stay UNKNOWN until they are calibrated too.
    """
    justified = measured.justified_confidence
    return ConfidenceGate(thresholds={
        "hero_cards": justified,
        "board_cards": 1.0,
        "street": 1.0,
        "pot": 1.0,
        "stacks": 1.0,
        "bet_size": 1.0,
        "action": 1.0,
    })


def _load_templates(directory: Path) -> dict:
    if not directory.is_dir():
        raise LiveCaptureError(f"template directory missing: {directory}")
    templates = {
        path.stem: cv2.imread(str(path)) for path in sorted(directory.glob("*.png"))
    }
    if not templates:
        raise LiveCaptureError(f"no templates found in {directory}")
    return templates


def load_calibration(
    platform: str = DEFAULT_PLATFORM, layout: str = DEFAULT_LAYOUT
) -> tuple[TableMap, VisionEngine]:
    """Load a platform's committed calibration into a ready VisionEngine."""
    table_map_path = _REPO_ROOT / "configs" / "platform" / f"{platform}__{layout}.json"
    vision_dir = _REPO_ROOT / "configs" / "vision" / platform
    if not table_map_path.is_file():
        raise LiveCaptureError(
            f"no calibration for {platform}/{layout}: {table_map_path}"
        )

    table_map = TableMap.from_json(table_map_path.read_text())
    calibration_data = json.loads((vision_dir / "calibration.json").read_text())
    template_source = calibration_data.get("template_source", platform)
    template_dir = _REPO_ROOT / "configs" / "vision" / template_source
    hero_layout = hero_layout_from_dict(
        json.loads((vision_dir / "hero_slot_layout.json").read_text())
    )

    card_recognizer = CornerGlyphCardRecognizer(
        CornerGlyphTemplateSet(
            rank_templates=_load_templates(template_dir / "rank"),
            suit_templates=_load_templates(template_dir / "suit"),
            version=f"{platform}-{layout}-v1",
        )
    )

    # Board / pot / action are not calibrated for this platform yet. They are
    # wired with placeholder detectors so the engine reports them UNKNOWN
    # rather than being unable to run at all; the TableMap has no ROI for
    # them, so these are never actually consulted.
    board_layout = BoardSlotLayout(
        layout_id=f"{layout}_board_uncalibrated",
        version=1,
        slots=tuple(
            CardSubROI(x=i * 0.2, y=0.0, width=0.19, height=1.0) for i in range(5)
        ),
    )
    _placeholder_rank = cv2.imread(
        str(next((template_dir / "rank").glob("*.png")))
    )
    amount_recognizer = TemplateAmountRecognizer(
        DigitTemplateSet(
            templates={"0": _placeholder_rank}, version="uncalibrated"
        )
    )
    action_recognizer = TemplateActionRecognizer(
        ActionTemplateSet(
            templates={ActionType.FOLD: cv2.imread(
                str(next((template_dir / "suit").glob("*.png")))
            )},
            version="uncalibrated",
        )
    )

    measured = load_measured_calibration(vision_dir)
    card_calibrator = measured.to_calibrator("card")
    # Fields with no calibration measurement of their own get a calibrator
    # that can never clear a gate: nothing has been measured about them, so
    # they must read UNKNOWN rather than borrow the card measurement's
    # credibility.
    calibrators = {"card": card_calibrator}
    for name in ("amount", "action", "street", "board"):
        calibrators[name] = _uncalibrated(name)
    manifest = VisionAssetManifest(
        platform_id=platform,
        layout_id=layout,
        card_layout_version=1,
        template_set_version=f"{platform}-v1",
        calibration_version=1,
        recognizer_versions={
            "card": "1", "amount": "1", "action": "1", "street": "1", "board": "1",
        },
    )

    engine = VisionEngine(
        board_layout=board_layout,
        hero_layout=hero_layout,
        card_recognizer=card_recognizer,
        board_slot_detector=TemplateBoardSlotDetector(board_layout),
        street_detector=TemplateStreetDetector(),
        amount_recognizer=amount_recognizer,
        action_recognizer=action_recognizer,
        calibrators=calibrators,
        manifest=manifest,
        bet_size_semantics=None,
    )
    return table_map, engine


class DeviceFrameSource:
    """FrameSource that captures one explicit ADB device on every pull."""

    def __init__(
        self,
        backend: CaptureService,
        device_serial: str,
    ) -> None:
        self._backend = backend
        self._target = CaptureTarget(window_id=device_serial)

    def next_frame(self) -> Frame | None:
        try:
            return self._backend.capture(self._target)
        except CaptureError as exc:
            raise LiveCaptureError(str(exc)) from exc


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


def _seed_state(hand_id: str = "live-1") -> PokerState:
    """An empty preflop state; recognition drives every field from here."""
    return PokerState(
        state_version=0,
        hand_id=hand_id,
        street=Street.PREFLOP,
        hero_cards=(),
        board_cards=(),
        players=(_seed_player(0, hero=True), _seed_player(1, hero=False)),
        pot=ChipAmount("0"),
        current_bet=ChipAmount("0"),
        to_call=ChipAmount("0"),
        actor=None,
    )


def build_pipeline(
    device_serial: str = DEFAULT_DEVICE_SERIAL,
    platform: str = DEFAULT_PLATFORM,
    layout: str = DEFAULT_LAYOUT,
) -> RealtimePipeline:
    """Assemble a pipeline reading raw portrait frames from LDPlayer."""
    table_map, vision = load_calibration(platform, layout)
    measured = load_measured_calibration(_REPO_ROOT / "configs" / "vision" / platform)
    orchestrator = ApplicationOrchestrator(
        state_engine=StateEngine(),
        hand_memory=InMemoryHandMemory(),
        confidence_gate=build_confidence_gate(measured),
    )
    next_hand_number = 1

    def next_hand_state() -> PokerState:
        nonlocal next_hand_number
        next_hand_number += 1
        return _seed_state(hand_id=f"live-{next_hand_number}")

    orchestrator.start_hand(_seed_state(hand_id="live-1"))
    frame_source = DeviceFrameSource(build_capture_backend(), device_serial)
    return RealtimePipeline(
        frame_source,
        vision,
        table_map,
        orchestrator,
        # A valid hero hand is immutable within a deal. Requiring two
        # identical frames prevents one half-rendered / miscaptured frame
        # from becoming the canonical hand shown to the player.
        hero_confirmation_frames=2,
        new_hand_state_factory=next_hand_state,
    )


async def live_analysis_stream(
    device_serial: str = DEFAULT_DEVICE_SERIAL,
    interval_seconds: float = 1.0,
) -> AsyncIterator[DesktopFrame]:
    """Yield fresh analysis while the selected ADB device is available.

    Capture and recognition are CPU-bound and run off the event loop, so the
    server stays responsive between frames.
    """
    try:
        pipeline = await asyncio.to_thread(
            build_pipeline, device_serial
        )
    except LiveCaptureError:
        raise
    except Exception as exc:
        raise LiveCaptureError(
            f"capture engine initialization failed: {exc}"
        ) from exc
    # Android recognition has not yet calibrated actor, stack, or action-line
    # inputs.  Keep the strategy session wired, but with no provider it must
    # emit an auditable ABSTAIN rather than inventing an action.
    strategy_session = LiveStrategySession(
        StrategyOrchestrator(StrategyRouter()),
        GameConfig(
            variant="NLHE",
            game_type=GameType.CASH,
            max_seats=2,
            dealt_player_count=2,
            small_blind=ChipAmount("1"),
            big_blind=ChipAmount("2"),
            minimum_chip=ChipAmount("1"),
        ),
    )
    while True:
        try:
            step = await asyncio.to_thread(pipeline.step)
        except (LiveCaptureError, TableMapError) as exc:
            raise LiveCaptureError(str(exc)) from exc
        except Exception as exc:
            raise LiveCaptureError(f"capture engine failed: {exc}") from exc
        if step is not None:
            yield strategy_session.frame(step.analysis, pipeline.current_state())
        await asyncio.sleep(interval_seconds)


__all__ = [
    "LiveCaptureError",
    "build_confidence_gate",
    "load_measured_calibration",
    "DeviceFrameSource",
    "build_capture_backend",
    "build_pipeline",
    "live_analysis_stream",
    "load_calibration",
    "DEFAULT_DEVICE_SERIAL",
]
