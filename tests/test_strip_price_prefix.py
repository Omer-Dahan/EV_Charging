"""Tests for the strip_price_prefix() station name cleaning function."""

import sys
import os
import unittest

# Make sure the data package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.build_db import strip_price_prefix


class TestStripPricePrefix(unittest.TestCase):
    """Test strip_price_prefix with various inputs."""

    def test_double_dollar_prefix(self):
        """$$ at start with space — typical real-world case."""
        self.assertEqual(strip_price_prefix("$$ מכבי נתניה"), "מכבי נתניה")

    def test_single_dollar_prefix(self):
        """Single $ at start."""
        self.assertEqual(strip_price_prefix("$ תחנת הרכבת"), "תחנת הרכבת")

    def test_triple_dollar_prefix(self):
        """$$$ at start."""
        self.assertEqual(strip_price_prefix("$$$ מלון דן"), "מלון דן")

    def test_dollars_no_space(self):
        """$$ without trailing space."""
        self.assertEqual(strip_price_prefix("$$מכבי"), "מכבי")

    def test_dollars_multiple_spaces(self):
        """$$ with multiple trailing spaces should be cleaned."""
        self.assertEqual(strip_price_prefix("$$   מועצה מקומית"), "מועצה מקומית")

    def test_shekel_prefix(self):
        """₪ sign at start is also stripped."""
        self.assertEqual(strip_price_prefix("₪₪ תחנה"), "תחנה")

    def test_mixed_dollar_shekel(self):
        """Mixed $ and ₪ at start."""
        self.assertEqual(strip_price_prefix("$₪ תחנה"), "תחנה")

    def test_no_dollar_unchanged(self):
        """Name without dollar sign should not change."""
        self.assertEqual(strip_price_prefix("תחנת חיפה"), "תחנת חיפה")

    def test_dollar_in_middle_unchanged(self):
        """Dollar sign in the MIDDLE of the name should NOT be touched."""
        self.assertEqual(strip_price_prefix("קפה $ הפסקה"), "קפה $ הפסקה")

    def test_only_dollars_stays(self):
        """If the name is ONLY dollar signs, return as-is (safety)."""
        self.assertEqual(strip_price_prefix("$$"), "$$")

    def test_only_dollars_and_spaces_stays(self):
        """Only dollars and spaces — return original (safety)."""
        self.assertEqual(strip_price_prefix("$$  "), "$$  ")

    def test_empty_string(self):
        """Empty string returns empty string."""
        self.assertEqual(strip_price_prefix(""), "")

    def test_none_returns_empty(self):
        """None input returns empty string."""
        self.assertEqual(strip_price_prefix(None), "")

    def test_real_data_villa(self):
        """Real data: $$ וילה דללוצ'ה | NH Energy."""
        self.assertEqual(
            strip_price_prefix("$$ וילה דללוצ'ה | NH Energy"),
            "וילה דללוצ'ה | NH Energy",
        )

    def test_real_data_mitar(self):
        """Real data: $$ מועצה מקומית מיתר AC."""
        self.assertEqual(
            strip_price_prefix("$$ מועצה מקומית מיתר AC"),
            "מועצה מקומית מיתר AC",
        )

    def test_real_data_kanion(self):
        """Real data: $$ קניון לב הרמה בית שמש | NH Energy."""
        self.assertEqual(
            strip_price_prefix("$$ קניון לב הרמה בית שמש | NH Energy"),
            "קניון לב הרמה בית שמש | NH Energy",
        )

    def test_whitespace_only_after_strip(self):
        """Name that becomes whitespace-only after stripping returns original."""
        self.assertEqual(strip_price_prefix("$   "), "$   ")

    def test_english_name_no_change(self):
        """English name without prefix is untouched."""
        self.assertEqual(strip_price_prefix("Tesla Supercharger"), "Tesla Supercharger")


if __name__ == "__main__":
    unittest.main()
