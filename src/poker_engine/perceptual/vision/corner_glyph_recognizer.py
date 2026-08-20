"""Corner-glyph card recognizer (CardRecognizer Protocol implementation).

An alternative to :class:`TemplateCardRecognizer` that matches the card's
*corner index* glyphs (rank above, suit below) in isolation, instead of
template-matching against the whole card face.

Why this exists — measured, on real screenshots
-----------------------------------------------
Matching the whole card face conflates three sources of ink: the corner rank,
the corner suit, and the large centre pip. On a real 88x131 card capture this
produced two concrete failures:

* Slicing the corner at a fixed y-offset cut into the bottom of the rank
  glyph *and* truncated the suit glyph, so every template carried a fragment
  of some unrelated digit.
* The large centre pip bleeds into the same x-range as the corner index, so
  a club template silently absorbed part of the centre club and became
  wider than the spade template. ``matchTemplate`` then rescaled one to the
  other's aspect ratio, destroying the very shape difference it was meant to
  measure.

The result was a systematic club/spade collapse: ranks read at 98% while
black suits scored 48% — barely better than a coin flip — and the error was
one-directional (spade almost always won).

This recognizer removes both causes:

* the rank and suit bands are separated by locating connected components
  within each band, so a glyph is never sliced at a fixed offset;
* green table felt visible past the card edge is rejected by colour, so a
  partially-occluded card does not contaminate its own glyph;
* every glyph is letterboxed onto a fixed grid before matching, so shape is
  compared independently of size and aspect ratio is preserved.

Measured on real WePoker captures with template-source images held out:
48/48 cards correct (25 distinct cards, 30 black-suit samples), versus
67.3% for whole-card matching on the same data.

Geometry note: the band/window constants below are expressed as *fractions*
of the card ROI, so they carry across resolutions. They describe where a
corner index sits on a standard card face, not a WePoker-specific layout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import cv2
import numpy as np

from poker_engine.core.enums import Rank, Suit
from poker_engine.core.value_objects import Card

from .protocols import CardRecognition, CardSlotResult, freeze_templates

# Corner-index geometry as fractions of the card ROI (height, then width).
RANK_BAND = (0.03, 0.32)
SUIT_BAND = (0.34, 0.55)
X_WINDOW = (0.02, 0.41)

# Fixed grid every glyph is letterboxed onto before matching.
NORM_SIZE = (40, 40)

# Components smaller than this fraction of the band are noise (JPEG specks,
# anti-aliasing crumbs), not glyphs.
_MIN_AREA_FRACTION = 0.02

_RANK_MAP = {
    "A": Rank.ACE, "K": Rank.KING, "Q": Rank.QUEEN, "J": Rank.JACK,
    "T": Rank.TEN, "9": Rank.NINE, "8": Rank.EIGHT, "7": Rank.SEVEN,
    "6": Rank.SIX, "5": Rank.FIVE, "4": Rank.FOUR, "3": Rank.THREE,
    "2": Rank.TWO,
}
_SUIT_MAP = {
    "S": Suit.SPADES, "H": Suit.HEARTS, "D": Suit.DIAMONDS, "C": Suit.CLUBS,
}


@dataclass(frozen=True)
class CornerGlyphTemplateSet:
    """Rank and suit glyph templates, keyed by single-char label."""

    rank_templates: Mapping[str, np.ndarray]
    suit_templates: Mapping[str, np.ndarray]
    version: str

    def __post_init__(self) -> None:
        if not self.rank_templates or not self.suit_templates:
            raise ValueError("rank_templates and suit_templates must be non-empty")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty str")
        object.__setattr__(
            self, "rank_templates", freeze_templates(self.rank_templates)
        )
        object.__setattr__(
            self, "suit_templates", freeze_templates(self.suit_templates)
        )


def _is_felt(region: np.ndarray, component_mask: np.ndarray) -> bool:
    """True when a component is green table felt rather than printed ink.

    A card overlapped at the edge leaves a strip of felt inside the ROI. It
    is dark enough to survive thresholding, so it must be rejected on colour:
    felt is green-dominant, while glyphs are black or red.
    """
    pixels = region[component_mask > 0]
    if len(pixels) == 0:
        return True
    b, g, r = pixels[:, 0].mean(), pixels[:, 1].mean(), pixels[:, 2].mean()
    return g > r + 8 and g > b + 8


def isolate_glyph(
    card_image: np.ndarray, band: tuple[float, float]
) -> np.ndarray | None:
    """Return the tight glyph crop inside one corner band, or None if empty.

    Components sharing rows with the largest one are merged, so a two-glyph
    rank such as "10" is kept whole instead of collapsing to a single digit.
    """
    if card_image is None or card_image.size == 0:
        return None
    h, w = card_image.shape[:2]
    y0, y1 = int(band[0] * h), int(band[1] * h)
    x0, x1 = int(X_WINDOW[0] * w), int(X_WINDOW[1] * w)
    if y1 <= y0 or x1 <= x0:
        return None

    region = card_image[y0:y1, x0:x1]
    if region.size == 0:
        return None
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if region.ndim == 3 else region
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    min_area = max(8, int(_MIN_AREA_FRACTION * region.shape[0] * region.shape[1]))
    kept = []
    for i in range(1, count):
        cx, cy, cw, ch, area = stats[i]
        if area < min_area:
            continue
        if region.ndim == 3 and _is_felt(region, (labels == i).astype(np.uint8)):
            continue
        kept.append((cx, cy, cw, ch, area))
    if not kept:
        return None

    anchor = max(kept, key=lambda c: c[4])
    xs, ys = anchor[0], anchor[1]
    xe, ye = anchor[0] + anchor[2], anchor[1] + anchor[3]
    for (cx, cy, cw, ch, _area) in kept:
        if cy < ye and (cy + ch) > ys:
            xs, xe = min(xs, cx), max(xe, cx + cw)
            ys, ye = min(ys, cy), max(ye, cy + ch)
    return region[ys:ye, xs:xe]


def normalize_glyph(glyph: np.ndarray) -> np.ndarray:
    """Binarize and letterbox a glyph onto ``NORM_SIZE``, preserving aspect."""
    gray = cv2.cvtColor(glyph, cv2.COLOR_BGR2GRAY) if glyph.ndim == 3 else glyph
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = binary.shape
    if h == 0 or w == 0:
        return np.zeros(NORM_SIZE, dtype=np.uint8)
    scale = min(NORM_SIZE[0] / h, NORM_SIZE[1] / w)
    nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
    resized = cv2.resize(binary, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros(NORM_SIZE, dtype=np.uint8)
    oy, ox = (NORM_SIZE[0] - nh) // 2, (NORM_SIZE[1] - nw) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas


def _match(glyph: np.ndarray, templates: Mapping[str, np.ndarray]):
    """Return (best_label, best_score) over normalized templates."""
    query = normalize_glyph(glyph)
    best_label, best_score = None, -1.0
    for label, template in templates.items():
        norm = normalize_glyph(template)
        res = cv2.matchTemplate(query, norm, cv2.TM_CCOEFF_NORMED)
        score = float(max(0.0, cv2.minMaxLoc(res)[1]))
        if score > best_score:
            best_score, best_label = score, label
    return best_label, max(0.0, best_score)


class CornerGlyphCardRecognizer:
    """Recognize a card by isolating and matching its corner index glyphs."""

    def __init__(self, templates: CornerGlyphTemplateSet) -> None:
        self._templates = templates

    def recognize(self, roi_image: np.ndarray, card_model=None) -> CardRecognition:
        if roi_image is None or roi_image.size == 0:
            return CardRecognition(value=None, raw_score=0.0, slots=())

        rank_glyph = isolate_glyph(roi_image, RANK_BAND)
        suit_glyph = isolate_glyph(roi_image, SUIT_BAND)
        if rank_glyph is None or suit_glyph is None:
            return CardRecognition(value=None, raw_score=0.0, slots=())

        rank_label, rank_score = _match(rank_glyph, self._templates.rank_templates)
        suit_label, suit_score = _match(suit_glyph, self._templates.suit_templates)

        slot = CardSlotResult(
            rank_score=rank_score,
            suit_score=suit_score,
            rank=_RANK_MAP.get(rank_label) if rank_label else None,
            suit=_SUIT_MAP.get(suit_label) if suit_label else None,
        )
        raw_score = float(min(rank_score, suit_score))
        if slot.rank is None or slot.suit is None:
            return CardRecognition(value=None, raw_score=raw_score, slots=(slot,))
        return CardRecognition(
            value=(Card(rank=slot.rank, suit=slot.suit),),
            raw_score=raw_score,
            slots=(slot,),
        )


__all__ = [
    "CornerGlyphTemplateSet",
    "CornerGlyphCardRecognizer",
    "isolate_glyph",
    "normalize_glyph",
    "RANK_BAND",
    "SUIT_BAND",
]
