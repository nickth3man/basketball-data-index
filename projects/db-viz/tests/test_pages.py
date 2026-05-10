"""Run every Streamlit page through AppTest and assert no exceptions.

Each page is parametrized so pytest reports per-page pass/fail and so the
runtime of each page contributes to coverage measurement.

Also runnable as a script: `python tests/test_pages.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PAGES = [
    "app.py",
    "pages/01_Home.py",
    "pages/02_Team_Profile.py",
    "pages/03_Player_Profile.py",
    "pages/04_Game_Center.py",
    "pages/05_Shot_Charts.py",
    "pages/06_PBP_Browser.py",
    "pages/07_Quarter_Splits.py",
    "pages/08_Officials.py",
    "pages/09_Odds_and_Betting.py",
    "pages/10_Schedule.py",
    "pages/11_Arenas.py",
    "pages/12_Season_Trends.py",
    "pages/13_Compare.py",
    "pages/14_SQL_Lab.py",
]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception(page: str) -> None:
    """Every page renders end-to-end with default sidebar selections."""
    at = AppTest.from_file(str(ROOT / page), default_timeout=120)
    at.run()
    if at.exception:
        msgs = "\n".join(str(e.value) for e in at.exception)
        pytest.fail(f"{page} raised:\n{msgs}")


if __name__ == "__main__":
    failures = []
    for page in PAGES:
        print(f"  testing {page} ...", end=" ", flush=True)
        try:
            test_page_runs_without_exception(page)
            print("OK")
        except Exception as e:
            failures.append((page, str(e)))
            print(f"FAIL ({e})")

    print()
    if failures:
        print(f"{len(failures)}/{len(PAGES)} pages FAILED:")
        for page, msg in failures:
            print(f"  - {page}: {msg}")
        sys.exit(1)
    print(f"All {len(PAGES)} pages passed.")
