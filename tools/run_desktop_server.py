"""Dev entry point: run the desktop server without an editable install.

    ./.venv/bin/python tools/run_desktop_server.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poker_engine.desktop.server import DEFAULT_WINDOW_TITLE, run  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the PokerSense local server")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    parser.add_argument("--window-index", type=int)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(port=args.port, window_title=args.window_title, window_index=args.window_index)
