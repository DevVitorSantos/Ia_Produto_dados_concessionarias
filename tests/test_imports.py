from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_queries_analytics_can_be_imported_before_services() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from queries.analytics import AnalyticsQueries"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
