"""Realtime analysis layer (Task 8).

Ties FrameSource -> Vision -> StateEngine -> analysis output together via an
event-driven loop. Produces a realtime state + equity + confidence snapshot;
does NOT auto-operate the table or recommend actions.
"""

from .analysis import (
    ConfidenceSnapshot,
    EquitySnapshot,
    RealtimeAnalysis,
    StateSnapshot,
)
from .change_detector import ChangeReport, detect_change
from .equity import (
    EquityStrategy,
    ExactRandomRangeEquity,
    MonteCarloRandomRangeEquity,
)
from .frame_source import FrameSource, SyntheticFrameSource
from .pipeline import PipelineStep, RealtimePipeline

__all__ = [
    "FrameSource",
    "SyntheticFrameSource",
    "ChangeReport",
    "detect_change",
    "StateSnapshot",
    "EquitySnapshot",
    "ConfidenceSnapshot",
    "RealtimeAnalysis",
    "EquityStrategy",
    "MonteCarloRandomRangeEquity",
    "ExactRandomRangeEquity",
    "RealtimePipeline",
    "PipelineStep",
]
