"""JSON wire contract for the desktop UI.

One function, one direction (engine -> UI). This must stay in sync with
``ui/app.js``'s expected shape:

    {
      "frame_seq": int,
      "state": {"street": str, "hero_cards": [str], "board_cards": [str], "pot": str},
      "equity": {"win_rate": float, "tie_rate": float},
      "confidence": {"overall_confidence": float, "field_status": [[str, str], ...]},
    }

Money is stringified (project-wide convention, see docs/serialization.md);
everything else is plain JSON-safe primitives so the frontend needs no
knowledge of the engine's internal value objects.
"""

from __future__ import annotations

from poker_engine.realtime.analysis import RealtimeAnalysis


def analysis_to_dict(analysis: RealtimeAnalysis) -> dict:
    if not isinstance(analysis, RealtimeAnalysis):
        raise TypeError("analysis must be a RealtimeAnalysis")
    state = analysis.state
    return {
        "frame_seq": analysis.frame_seq,
        "state": {
            "street": state.street.value,
            "hero_cards": [str(c) for c in state.hero_cards],
            "board_cards": [str(c) for c in state.board_cards],
            "pot": str(state.pot.value),
        },
        "equity": {
            "win_rate": analysis.equity.win_rate,
            "tie_rate": analysis.equity.tie_rate,
        },
        "confidence": {
            "overall_confidence": analysis.confidence.overall_confidence,
            "field_status": [list(pair) for pair in analysis.confidence.field_status],
        },
    }


__all__ = ["analysis_to_dict"]
