"""Action recognizer (per-seat, seat-rendered action label/state).

Consumes a per-seat ACTION ROI image (with slot_id) and recognizes the
seat-rendered action label: FOLD/CHECK/CALL/BET/RAISE/ALL_IN/UNKNOWN.

This is OBSERVED player action, NOT Hero clickable buttons. If a platform does
not expose per-seat action visual signal, the caller must raise a Platform
Visual Gap — this module never guesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import cv2
import numpy as np

from poker_engine.core.enums import ActionType

from .protocols import ActionRecognition, freeze_templates


@dataclass(frozen=True)
class ActionTemplateSet:
    templates: Mapping[ActionType, np.ndarray]
    version: str

    def __post_init__(self) -> None:
        if not self.templates:
            raise ValueError("templates must be non-empty")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty str")
        object.__setattr__(self, "templates", freeze_templates(self.templates))


class TemplateActionRecognizer:
    """Recognize a seat action label via template matching."""

    def __init__(self, templates: ActionTemplateSet, min_score: float = 0.5) -> None:
        self._templates = templates
        self._min_score = min_score

    def recognize(self, roi_image: np.ndarray, slot_id: int) -> ActionRecognition:
        if roi_image is None or roi_image.size == 0:
            return ActionRecognition(value=None, raw_score=0.0)

        gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
        best = None
        best_score = -1.0
        for action, tmpl in self._templates.templates.items():
            if tmpl.ndim == 3:
                tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
            else:
                tmpl_gray = tmpl
            if tmpl_gray.shape[0] > gray.shape[0] or tmpl_gray.shape[1] > gray.shape[1]:
                tmpl_gray = cv2.resize(tmpl_gray, (gray.shape[1], gray.shape[0]))
            res = cv2.matchTemplate(gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
            _, maxval, _, _ = cv2.minMaxLoc(res)
            score = max(0.0, maxval)
            if score > best_score:
                best_score = score
                best = action

        # A low best score means "no action rendered" -> abstain from guessing.
        if best_score < self._min_score:
            return ActionRecognition(value=None, raw_score=float(best_score))
        return ActionRecognition(value=best, raw_score=float(best_score))


__all__ = ["ActionTemplateSet", "TemplateActionRecognizer"]
