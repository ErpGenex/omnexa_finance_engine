# Copyright (c) 2026, ErpGenEx
from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.fs_parity_bridge import preview_gl_for_vertical


class TestFsParityBridge(FrappeTestCase):
	def test_mortgage_default_scenario(self):
		out = preview_gl_for_vertical("mortgage", principal="1000")
		self.assertEqual(out["scenario"], "loan_disbursement")
		self.assertEqual(len(out["lines"]), 2)

	def test_leasing_recognition(self):
		out = preview_gl_for_vertical(
			"leasing", scenario="lease_recognition", rou_asset="50", lease_liability="50"
		)
		self.assertEqual(out["scenario"], "lease_recognition")
