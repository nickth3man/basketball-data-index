"""Formatting helpers for st.metric and table cells."""

from __future__ import annotations


def fmt_int(n) -> str:
    if n is None:
        return "—"
    return f"{int(n):,}"


def fmt_pct(p, decimals: int = 1) -> str:
    if p is None:
        return "—"
    return f"{float(p) * 100:.{decimals}f}%"


def fmt_float(x, decimals: int = 2) -> str:
    if x is None:
        return "—"
    return f"{float(x):.{decimals}f}"


def fmt_human(n) -> str:
    """Compact display: 1.2M, 14.4K, etc."""
    if n is None:
        return "—"
    n = float(n)
    for unit, scale in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= scale:
            return f"{n / scale:.1f}{unit}"
    return f"{n:.0f}"
