"""Tests for real benchmark adapter platform/layout metadata validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

_spec = importlib.util.spec_from_file_location(
    "run_benchmark", _ROOT / "tools" / "run_benchmark.py"
)
run_benchmark = importlib.util.module_from_spec(_spec)
sys.modules["run_benchmark"] = run_benchmark
_spec.loader.exec_module(run_benchmark)

_FRAME = str(_ROOT / "datasets" / "golden" / "real" / "frames" / "sample_0.png")


def _golden(**sample_overrides):
    sample = {
        "image_path": _FRAME,
        "platform_id": "wpk",
        "layout_id": "6max",
        "sample_id": "real-0",
        "source": "real-platform",
        "ground_truth": {"street": "PREFLOP", "pot": "10", "bet_size": "5"},
    }
    sample.update(sample_overrides)
    return {"samples": [sample]}


def test_real_adapter_matching_metadata_runs():
    entries = run_benchmark._run_real_obj(_golden())
    assert len(entries) == 1
    assert "street" in entries[0]
    # stable sample_id preserved from the descriptor
    assert entries[0]["_sample_id"] == "real-0"


def test_real_adapter_missing_sample_id_fails():
    golden = _golden()
    golden["samples"][0].pop("sample_id")
    with pytest.raises(ValueError) as exc:
        run_benchmark._run_real_obj(golden)
    assert "sample_id" in str(exc.value)


def test_real_adapter_wrong_platform_fails():
    golden = _golden(platform_id="OTHER")
    with pytest.raises(ValueError) as exc:
        run_benchmark._run_real_obj(golden)
    assert "platform_id" in str(exc.value)


def test_real_adapter_wrong_layout_fails():
    golden = _golden(layout_id="9max")
    with pytest.raises(ValueError) as exc:
        run_benchmark._run_real_obj(golden)
    assert "layout_id" in str(exc.value)
