#!/usr/bin/env python3
"""Smoke-test the email-safe HTML brief renderer."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "refresh-brief.py"


def load_brief_module():
    spec = importlib.util.spec_from_file_location("refresh_brief", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EmailHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.brief = load_brief_module()
        cls.payload = json.loads((ROOT / "brief-data.json").read_text(encoding="utf-8"))

    def test_email_contains_core_sections(self) -> None:
        html = self.brief.format_email_html(self.payload)
        self.assertIn("Daily Investment Brief", html)
        self.assertIn("Market Read", html)
        self.assertIn("Market Snapshot", html)
        self.assertIn("border-left:4px solid #b85a28", html)
        self.assertIn("Bitcoin", html)
        self.assertIn("Strategy", html)
        self.assertNotIn("<script", html.lower())

    def test_percentages_are_colorized(self) -> None:
        colored = self.brief.colorize_market_read(
            "Bitcoin is at $83,343, +0.11% on the day and −0.28% versus gold."
        )
        self.assertIn('<strong style="color:#1a1714;">$83,343</strong>', colored)
        self.assertIn("color:#0c6b45", colored)
        self.assertIn("color:#9d342c", colored)
        self.assertIn("+0.11%", colored)
        unsigned = self.brief.colorize_market_read(
            "Across five sessions, Bitcoin is 0.52% higher."
        )
        self.assertIn("0.52% higher", unsigned)
        self.assertNotIn("color:#0c6b45", unsigned)


if __name__ == "__main__":
    unittest.main()
