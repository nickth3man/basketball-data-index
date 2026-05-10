"""Cover the Team-vs-Team branch of pages/13_Compare.py via session-state poke."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize("mode", ["Player vs Player", "Team vs Team"])
def test_compare_radio_modes(mode: str) -> None:
    """Exercise both modes of the Compare page."""
    at = AppTest.from_file(str(ROOT / "pages" / "13_Compare.py"), default_timeout=120)
    at.run()
    # Find the radio widget and select the alternate mode
    if at.exception:
        pytest.fail(f"first run errored: {[str(e.value) for e in at.exception]}")
    if mode == "Team vs Team":
        radios = at.radio
        if radios:
            radios[0].set_value(mode).run()
            if at.exception:
                pytest.fail(f"Team vs Team mode raised: {[str(e.value) for e in at.exception]}")
