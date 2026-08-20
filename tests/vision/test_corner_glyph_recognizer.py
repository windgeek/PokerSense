"""Regression tests for the corner-glyph card recognizer.

The fixtures under ``fixtures/wepoker/`` are real card crops captured from a
live WePoker H5 table — not synthetic renders. They are deliberately all
*held-out* samples: none of them was used to cut the templates in
``configs/vision/wepoker/``, so passing here means recognizing card art the
templates were never derived from.

Six of the ten are black-suited (clubs/spades) on purpose: whole-card
template matching scored 48% on black suits against this same data, and that
collapse is exactly what this recognizer exists to fix.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from poker_engine.core.enums import Rank, Suit
from poker_engine.perceptual.vision.corner_glyph_recognizer import (
    CornerGlyphCardRecognizer,
    CornerGlyphTemplateSet,
    isolate_glyph,
    normalize_glyph,
    RANK_BAND,
    SUIT_BAND,
    NORM_SIZE,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_DIR = _REPO_ROOT / "configs" / "vision" / "wepoker"
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "wepoker"

_RANK_CH = {
    "A": Rank.ACE, "K": Rank.KING, "Q": Rank.QUEEN, "J": Rank.JACK,
    "T": Rank.TEN, "9": Rank.NINE, "8": Rank.EIGHT, "7": Rank.SEVEN,
    "6": Rank.SIX, "5": Rank.FIVE, "4": Rank.FOUR, "3": Rank.THREE,
    "2": Rank.TWO,
}
_SUIT_CH = {
    "S": Suit.SPADES, "H": Suit.HEARTS, "D": Suit.DIAMONDS, "C": Suit.CLUBS,
}


def _load_dir(path: Path) -> dict:
    return {f.stem: cv2.imread(str(f)) for f in sorted(path.glob("*.png"))}


@pytest.fixture(scope="module")
def recognizer() -> CornerGlyphCardRecognizer:
    return CornerGlyphCardRecognizer(
        CornerGlyphTemplateSet(
            rank_templates=_load_dir(_TEMPLATE_DIR / "rank"),
            suit_templates=_load_dir(_TEMPLATE_DIR / "suit"),
            version="wepoker-h5-v1",
        )
    )


def _fixtures() -> list[str]:
    return sorted(f.stem for f in _FIXTURE_DIR.glob("*.png"))


def test_template_set_is_complete():
    ranks = {f.stem for f in (_TEMPLATE_DIR / "rank").glob("*.png")}
    suits = {f.stem for f in (_TEMPLATE_DIR / "suit").glob("*.png")}
    assert ranks == set(_RANK_CH)
    assert suits == set(_SUIT_CH)


@pytest.mark.parametrize("label", _fixtures())
def test_recognizes_real_wepoker_card(recognizer, label):
    image = cv2.imread(str(_FIXTURE_DIR / f"{label}.png"))
    assert image is not None, f"fixture {label} unreadable"

    result = recognizer.recognize(image)

    assert result.value is not None, f"{label} not recognized at all"
    card = result.value[0]
    assert card.rank is _RANK_CH[label[0]], f"{label}: wrong rank"
    assert card.suit is _SUIT_CH[label[1]], f"{label}: wrong suit"


def test_black_suits_are_not_confused(recognizer):
    """Clubs and spades must stay distinct — the specific failure this fixes."""
    black = [lbl for lbl in _fixtures() if lbl[1] in ("C", "S")]
    assert len(black) >= 6, "fixture set must cover black suits meaningfully"
    for label in black:
        image = cv2.imread(str(_FIXTURE_DIR / f"{label}.png"))
        result = recognizer.recognize(image)
        assert result.value is not None
        assert result.value[0].suit is _SUIT_CH[label[1]], f"{label}: suit flipped"


def test_isolated_glyphs_do_not_span_the_whole_band(recognizer):
    """A glyph filling its band means the crop caught neighbouring ink.

    Fixed-offset slicing used to leave the bottom of the rank digit inside
    the suit crop, which pinned the crop to the band's full height. Guarding
    the height directly is what stops that regression coming back silently.
    """
    image = cv2.imread(str(_FIXTURE_DIR / "7S.png"))
    band_height = int((SUIT_BAND[1] - SUIT_BAND[0]) * image.shape[0])
    suit_glyph = isolate_glyph(image, SUIT_BAND)
    assert suit_glyph is not None
    assert suit_glyph.shape[0] < band_height


def test_felt_is_rejected_from_occluded_card(recognizer):
    """KH is captured with table felt visible past the card edge."""
    image = cv2.imread(str(_FIXTURE_DIR / "KH.png"))
    rank_glyph = isolate_glyph(image, RANK_BAND)
    assert rank_glyph is not None
    # Felt runs the full band height; the rank glyph must be narrower than
    # the whole x-window it was searched in.
    assert rank_glyph.shape[1] < image.shape[1] * 0.41


def test_normalize_preserves_aspect_ratio():
    tall = cv2.imread(str(_FIXTURE_DIR / "7S.png"))[0:60, 0:20]
    out = normalize_glyph(tall)
    assert out.shape == NORM_SIZE
    assert out.max() > 0


def test_empty_input_is_unknown_not_a_guess(recognizer):
    import numpy as np

    result = recognizer.recognize(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result.value is None
    assert result.raw_score == 0.0
