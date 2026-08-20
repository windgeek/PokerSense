"""First real-world Vision proof: capture -> real VisionEngine -> RawObservation.

Not a real poker platform (see project notes on why WePoker specifically is
parked). This captures our own rendered `mock_table.html` (a real on-screen
window, real pixels, real macOS Quartz capture) and runs it through the real,
unmodified VisionEngine / recognizers / calibrators -- to answer "does the
actual recognition code work against actual captured pixels" for the first
time in this project's history. Card-skin-specific accuracy is NOT the goal
here; end-to-end wiring correctness is.

Usage: serve tools/real_pipeline_smoke/mock_table.html, open it in a real
browser window (e.g. `open -a Safari http://localhost:8944/mock_table.html`),
then run this script.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2  # noqa: E402

from poker_engine.perceptual.capture.base import CaptureTarget  # noqa: E402
from poker_engine.perceptual.capture.quartz_backend import QuartzBackend  # noqa: E402
from vision_setup import WINDOW_TITLE, build  # noqa: E402

OUT_DIR = Path("/tmp/pokersense_smoke")
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    backend = QuartzBackend()
    frame = backend.capture(CaptureTarget(window_id=WINDOW_TITLE))
    print(f"captured frame: {frame.width}x{frame.height}")
    cv2.imwrite(str(OUT_DIR / "captured.png"), frame.image)

    table_map, engine = build(frame)
    obs = engine.process(frame, table_map)

    def _fmt(field):
        return (
            f"{field.value!r} conf={field.confidence:.2f} "
            f"status={field.validation_status.value}"
        )

    print("--- RawObservation (from a REAL captured screenshot) ---")
    print("hero_cards :", _fmt(obs.hero_cards))
    print("board_cards:", _fmt(obs.board_cards))
    print("street     :", _fmt(obs.street))
    print("pot        :", _fmt(obs.pot))
    print("overall_confidence:", obs.overall_confidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
