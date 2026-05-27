#!/usr/bin/env python3
"""Smoke tests for regulatory status classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.card_regulatory import classify_regulatory_status


def test_fda_cleared() -> None:
    assert classify_regulatory_status("FDA De Novo / Class II classification. [8]") == "green"


def test_not_fda_approved() -> None:
    assert classify_regulatory_status("Not FDA approved / not described as a regulated medical device. [1]") == "red"


def test_ce_marked() -> None:
    assert classify_regulatory_status("Available in the EU; CE marked for clinical use.") == "blue"


def test_eua() -> None:
    assert classify_regulatory_status("Authorized under FDA emergency use authorization (EUA).") == "yellow"


def test_investigational() -> None:
    assert classify_regulatory_status("For investigational use only; IRB approval required.") == "orange"


def test_unknown() -> None:
    assert classify_regulatory_status("Not specified") == "gray"
    assert classify_regulatory_status("General workflow description without regulatory terms.") == "gray"


def test_fda_and_ce_prefers_green() -> None:
    text = "FDA-cleared in the U.S.; CE marked in Europe. [1]"
    assert classify_regulatory_status(text) == "green"


if __name__ == "__main__":
    test_fda_cleared()
    test_not_fda_approved()
    test_ce_marked()
    test_eua()
    test_investigational()
    test_unknown()
    test_fda_and_ce_prefers_green()
    print("All regulatory status tests passed.")
