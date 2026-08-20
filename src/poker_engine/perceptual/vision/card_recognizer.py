"""Card recognizer via OpenCV template matching (rank + suit independent).

MVP: match each rendered card position against a rank-template set and a
suit-template set. Exposes a TemplateCardRecognizer and a CardTemplateSet.

Low confidence -> UNKNOWN (value=None). Duplicate/impossible visible cards are
flags for the caller to turn into CONFLICT (per plan §5); this module does not
guess-correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import cv2
import numpy as np

from poker_engine.core.enums import Rank, Suit
from poker_engine.core.value_objects import Card

from .protocols import CardRecognition, CardSlotResult, freeze_templates

# Rank label -> Rank enum (supports single-char renders: "T" -> TEN).
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
class CardTemplateSet:
    """Rank and suit template images keyed by single-char label."""

    rank_templates: Mapping[str, np.ndarray]
    suit_templates: Mapping[str, np.ndarray]
    version: str

    def __post_init__(self) -> None:
        if not self.rank_templates or not self.suit_templates:
            raise ValueError("rank_templates and suit_templates must be non-empty")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty str")
        # deep-freeze: read-only mapping + read-only, copied ndarray values
        object.__setattr__(
            self, "rank_templates", freeze_templates(self.rank_templates)
        )
        object.__setattr__(
            self, "suit_templates", freeze_templates(self.suit_templates)
        )


def _best_match(image: np.ndarray, templates: Mapping[str, np.ndarray]):
    """Return (best_label, best_score, per_label_scores) via normalized match."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    best_label = None
    best_score = -1.0
    scores: dict[str, float] = {}
    for label, tmpl in templates.items():
        if tmpl.ndim == 3:
            tmpl = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
        if tmpl.shape[0] > gray.shape[0] or tmpl.shape[1] > gray.shape[1]:
            tmpl = cv2.resize(tmpl, (gray.shape[1], gray.shape[0]))
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, maxval, _, _ = cv2.minMaxLoc(res)
        # TM_CCOEFF_NORMED is in [-1,1]; clamp negatives to 0 so all vision
        # raw scores share a [0,1] "higher == stronger" convention.
        score = float(max(0.0, maxval))
        scores[label] = score
        if score > best_score:
            best_score = score
            best_label = label
    return best_label, best_score, scores


class TemplateCardRecognizer:
    """Recognize a single card image by rank+suit template matching."""

    def __init__(self, templates: CardTemplateSet) -> None:
        self._templates = templates

    def recognize(self, roi_image: np.ndarray, card_model=None) -> CardRecognition:
        if roi_image is None or roi_image.size == 0:
            return CardRecognition(value=None, raw_score=0.0, slots=())

        rank_label, rank_score, _ = _best_match(
            roi_image, self._templates.rank_templates
        )
        suit_label, suit_score, _ = _best_match(
            roi_image, self._templates.suit_templates
        )

        slot = CardSlotResult(
            rank_score=rank_score,
            suit_score=suit_score,
            rank=_RANK_MAP.get(rank_label) if rank_label else None,
            suit=_SUIT_MAP.get(suit_label) if suit_label else None,
        )
        raw_score = float(min(rank_score, suit_score))

        if slot.rank is None or slot.suit is None:
            return CardRecognition(value=None, raw_score=raw_score, slots=(slot,))

        card = Card(rank=slot.rank, suit=slot.suit)
        return CardRecognition(value=(card,), raw_score=raw_score, slots=(slot,))


__all__ = ["CardTemplateSet", "TemplateCardRecognizer"]
