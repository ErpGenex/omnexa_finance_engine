# Copyright (c) 2026, ErpGenEx
"""Wave B — all FS verticals can reach posting preview bridge."""

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.fs_parity_bridge import VERTICAL_DEFAULTS, preview_gl_for_vertical


class TestSapParityFsVerticals(FrappeTestCase):
	def test_all_fs_verticals_have_default_scenario(self):
		expected = {
			"leasing",
			"mortgage",
			"vehicle",
			"consumer",
			"factoring",
			"sme_retail",
			"credit_engine",
			"credit_risk",
			"alm",
		}
		self.assertEqual(set(VERTICAL_DEFAULTS.keys()), expected)

	def test_each_vertical_returns_lines(self):
		for vertical in VERTICAL_DEFAULTS:
			out = preview_gl_for_vertical(vertical, principal="100", rou_asset="100", lease_liability="100")
			self.assertGreaterEqual(len(out["lines"]), 2, vertical)
