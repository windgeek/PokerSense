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

__all__ = [
    "CaptureError",
    "CaptureService",
    "CaptureTarget",
    "Frame",
    "WindowRect",
    "FakeBackend",
    "MssBackend",
]
