"""Monotonic empirical-bin confidence calibration (MVP, no sklearn).

Maps a raw detector score to a calibrated confidence in [0,1] via piecewise-
constant monotonic bins learned from a calibration set.

The calibrator is NOT aware of Task 5 Frozen confidence thresholds. A detector
may additionally carry an ``abstain_floor`` (per-detector, versioned, learned
only from the calibration set) below which the raw score is considered
perceptually unreadable / out-of-domain.
"""

from __future__ import annotations

from dataclasses import dataclass

from .protocols import CalibratedConfidence, _check_raw_score


@dataclass(frozen=True)
class CalibrationBins:
    """A monotonic piecewise-constant mapping: raw score -> calibrated confidence.

    ``edges`` are strictly increasing raw-score boundaries (length N+1),
    ``confidence`` are N calibrated values for the N bins. The mapping is
    monotonic non-decreasing by construction (validated at build time).
    """

    edges: tuple[float, ...]          # N+1 strictly increasing
    confidence: tuple[float, ...]     # N values in [0,1]

    def __post_init__(self) -> None:
        edges = tuple(self.edges)
        conf = tuple(self.confidence)
        if len(edges) < 2:
            raise ValueError("need at least two edges (one bin)")
        if len(conf) != len(edges) - 1:
            raise ValueError("confidence must have len(edges)-1 entries")
        for e in edges:
            # each edge must be a finite value in [0,1] (raw-score domain)
            _check_raw_score(e, "edge")
        # strictly increasing edges (check after the finite/range check)
        for i in range(1, len(edges)):
            if edges[i] <= edges[i - 1]:
                raise ValueError("edges must be strictly increasing")
        for c in conf:
            if isinstance(c, bool) or not isinstance(c, (int, float)):
                raise TypeError("confidence must be numeric")
            if not (0.0 <= float(c) <= 1.0):
                raise ValueError("confidence must be in [0,1]")
        # monotonic non-decreasing
        for i in range(1, len(conf)):
            if conf[i] < conf[i - 1]:
                raise ValueError("confidence must be monotonic non-decreasing")
        object.__setattr__(self, "edges", tuple(float(e) for e in edges))
        object.__setattr__(self, "confidence", tuple(float(c) for c in conf))

    def map(self, raw_score: float) -> float:
        """Return calibrated confidence for a raw score (piecewise-constant)."""
        _check_raw_score(raw_score, "raw_score")
        if raw_score <= self.edges[0]:
            return self.confidence[0]
        if raw_score >= self.edges[-1]:
            return self.confidence[-1]
        for i in range(len(self.confidence)):
            if self.edges[i] <= raw_score < self.edges[i + 1]:
                return self.confidence[i]
        return self.confidence[-1]  # unreachable


@dataclass(frozen=True)
class ConfidenceCalibrator:
    """A named, versioned calibrator with an optional abstain floor."""

    name: str
    version: int
    bins: CalibrationBins
    abstain_floor: float | None = None   # per-detector, not a Task 5 threshold

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty str")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("version must be an int")
        if self.abstain_floor is not None:
            f = self.abstain_floor
            if isinstance(f, bool) or not isinstance(f, (int, float)):
                raise TypeError("abstain_floor must be a float or None")
            if not (0.0 <= float(f) <= 1.0):
                raise ValueError("abstain_floor must be in [0,1]")
            object.__setattr__(self, "abstain_floor", float(f))

    def calibrate(self, raw_score: float) -> CalibratedConfidence:
        _check_raw_score(raw_score, "raw_score")
        return CalibratedConfidence(confidence=self.bins.map(raw_score))

    def should_abstain(self, raw_score: float) -> bool:
        _check_raw_score(raw_score, "raw_score")
        return self.abstain_floor is not None and raw_score < self.abstain_floor


__all__ = ["CalibrationBins", "ConfidenceCalibrator"]
