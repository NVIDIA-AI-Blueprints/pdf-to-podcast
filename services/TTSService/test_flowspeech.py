"""Run only offline FlowSpeech tests; never the live service test_api module."""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    tests = Path(__file__).resolve().with_name("tests_flowspeech")
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "pytest", str(tests), f"--confcutdir={tests}", "-q"]
        )
    )
