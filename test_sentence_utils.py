"""Tests for sentence_utils."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from utils.sentence_utils import count_sentences, split_sentences


def test_us_abbreviation():
    assert count_sentences("Deployed in the U.S. for clinical use.") == 1


def test_decimal_percent():
    assert count_sentences("Sensitivity is 95.5% on validation set.") == 1


def test_url_in_sentence():
    text = "See https://example.com/model for details."
    assert count_sentences(text) == 1


def test_three_sentences():
    text = "Input is dermoscopy. Output is risk. Role is advisory."
    assert count_sentences(text) == 3
