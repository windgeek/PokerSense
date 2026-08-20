"""Capture subpackage: frame contracts and capture backends."""

from .base import (
    CaptureError,
    CaptureService,
    CaptureTarget,
    Frame,
    WindowRect,
)
from .fake_backend import FakeBackend
from .mss_backend import MssBackend
from .quartz_backend import QuartzBackend, WindowCandidate, list_window_candidates

__all__ = [
    "CaptureError",
    "CaptureService",
    "CaptureTarget",
    "Frame",
    "WindowRect",
    "FakeBackend",
    "MssBackend",
    "QuartzBackend",
    "WindowCandidate",
    "list_window_candidates",
]
