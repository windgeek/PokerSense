"""Build a real TableMap + VisionEngine calibrated against mock_table.html.

Extracted so both the one-shot smoke script (run_smoke.py) and the desktop
server's optional "real capture" mode can share the exact same, empirically
verified calibration -- see run_smoke.py's module docstring for what this
proves and does not prove.
"""

from __future__ import annotations

import cv2
import numpy as np

from poker_engine.core.enums import ActionType
from poker_engine.perceptual.capture.base import Frame
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
)
from poker_engine.perceptual.vision.card_layout import (
    BoardSlotLayout,
    CardSubROI,
    HeroSlotLayout,
)
from poker_engine.perceptual.vision.card_recognizer import (
    CardTemplateSet,
    TemplateCardRecognizer,
)
from poker_engine.perceptual.vision.engine import VisionEngine
from poker_engine.perceptual.vision.street_detector import TemplateStreetDetector
from poker_engine.perceptual.vision.table_map import ROI, ROIKind, TableMap

WINDOW_TITLE = "mock-table"

# --- geometry, in physical pixels of a captured 2648x1880 frame (measured
# via connected-component analysis of a real capture, not guessed) ---
BOARD_BOXES = [(80, 400, 180, 252), (288, 400, 180, 252), (496, 400, 180, 252),
               (704, 400, 180, 252), (912, 400, 180, 252)]
HERO_BOXES = [(80, 744, 180, 252), (288, 744, 180, 252)]
# Inset from the raw white-box bounds: rounded corners let the dark
# background show through at the very edge, which reads as spurious "ink"
# columns during character segmentation (learned by inspecting a capture).
POT_BOX = (80 + 14, 1088 + 14, 168 - 28, 122 - 28)
RANK_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
RANK_BOXES = [(128 + i * 136, 1374, 120, 140) for i in range(13)]
SUIT_ORDER = ["S", "H", "D", "C"]
SUIT_BOXES = [(128 + i * 136, 1586, 120, 140) for i in range(4)]


def _bbox_union(boxes):
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return x0, y0, x1 - x0, y1 - y0


def _roi(kind: ROIKind, box, ref_w: int, ref_h: int) -> ROI:
    x, y, w, h = box
    return ROI(kind=kind, x=x / ref_w, y=y / ref_h, width=w / ref_w, height=h / ref_h)


def _sub_rois(boxes, parent_box) -> list[CardSubROI]:
    px, py, pw, ph = parent_box
    return [
        CardSubROI(x=(x - px) / pw, y=(y - py) / ph, width=w / pw, height=h / ph)
        for (x, y, w, h) in boxes
    ]


def _crop(img: np.ndarray, box) -> np.ndarray:
    x, y, w, h = box
    return img[y:y + h, x:x + w].copy()


def _tight_crop(img: np.ndarray, pad: int = 4) -> np.ndarray:
    """Trim to the ink (dark-pixel) bounding box, plus a small margin.

    Template-matching a loosely-cropped glyph (lots of white margin) against
    a small corner-index glyph in situ scores badly (~0.15) because the
    template's white padding doesn't correspond to anything at the match
    site. Trimming to just the ink fixes this (verified empirically: 0.97
    vs 0.16 for the same glyph, same source image).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    mask = gray < 200
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img
    x0, x1 = max(0, xs.min() - pad), min(img.shape[1], xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(img.shape[0], ys.max() + pad + 1)
    return img[y0:y1, x0:x1].copy()


def build(frame: Frame) -> tuple[TableMap, VisionEngine]:
    """Build a (TableMap, VisionEngine) calibrated from a real captured frame."""
    ref_w, ref_h = frame.width, frame.height
    board_parent = _bbox_union(BOARD_BOXES)
    hero_parent = _bbox_union(HERO_BOXES)

    table_map = TableMap(
        platform_id="mock",
        layout_id="smoke",
        reference_size=(ref_w, ref_h),
        aspect_tolerance=0.02,
        rois=(
            _roi(ROIKind.BOARD_CARDS, board_parent, ref_w, ref_h),
            _roi(ROIKind.HERO_CARDS, hero_parent, ref_w, ref_h),
            _roi(ROIKind.POT, POT_BOX, ref_w, ref_h),
        ),
    )

    board_layout = BoardSlotLayout(
        layout_id="smoke", version=1, slots=tuple(_sub_rois(BOARD_BOXES, board_parent)),
    )
    hero_layout = HeroSlotLayout(
        layout_id="smoke", version=1, slots=tuple(_sub_rois(HERO_BOXES, hero_parent)),
    )

    rank_templates = {
        label: _tight_crop(_crop(frame.image, box))
        for label, box in zip(RANK_ORDER, RANK_BOXES)
    }
    suit_templates = {
        label: _tight_crop(_crop(frame.image, box))
        for label, box in zip(SUIT_ORDER, SUIT_BOXES)
    }
    card_recognizer = TemplateCardRecognizer(
        CardTemplateSet(
            rank_templates=rank_templates,
            suit_templates=suit_templates,
            version="smoke-1",
        )
    )

    # Digits actually rendered by mock_table.html's pot value ("42"): reuse
    # the rank-template crops (same font/size), avoiding a separate strip.
    digit_templates = DigitTemplateSet(
        templates={"2": rank_templates["2"], "4": rank_templates["4"]},
        version="smoke-1",
    )
    amount_recognizer = TemplateAmountRecognizer(digit_templates, min_score=0.3)

    # Never exercised (no ACTION ROIs declared) -- still needs a valid,
    # non-empty template set to construct.
    action_recognizer = TemplateActionRecognizer(
        ActionTemplateSet(
            templates={ActionType.FOLD: np.zeros((20, 20, 3), dtype=np.uint8)},
            version="smoke-1",
        )
    )

    board_detector = TemplateBoardSlotDetector(board_layout)
    street_detector = TemplateStreetDetector()

    bins = CalibrationBins(edges=(0.0, 0.4, 1.0), confidence=(0.2, 0.95))
    calibrators = {
        name: ConfidenceCalibrator(name=name, version=1, bins=bins, abstain_floor=0.3)
        for name in ("card", "amount", "action", "street", "board")
    }

    manifest = VisionAssetManifest(
        platform_id="mock", layout_id="smoke",
        card_layout_version=1, template_set_version="smoke-1",
        calibration_version=1,
        recognizer_versions={
            "card": "1", "amount": "1", "action": "1", "street": "1", "board": "1",
        },
    )

    engine = VisionEngine(
        board_layout=board_layout,
        hero_layout=hero_layout,
        card_recognizer=card_recognizer,
        board_slot_detector=board_detector,
        street_detector=street_detector,
        amount_recognizer=amount_recognizer,
        action_recognizer=action_recognizer,
        calibrators=calibrators,
        manifest=manifest,
        bet_size_semantics=None,
    )
    return table_map, engine


__all__ = ["WINDOW_TITLE", "build"]
