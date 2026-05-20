# Copyright (c) 2026, ErpGenEx
from decimal import Decimal

from frappe.tests.utils import FrappeTestCase

import frappe

from omnexa_finance_engine.fs_gl_posting import post_fs_scenario_gl


class TestFsGlPosting(FrappeTestCase):
	def test_post_scenario_respects_feature_flag(self):
		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No company")
		old = frappe.local.conf.get("omnexa_feature_flags")
		frappe.local.conf["omnexa_feature_flags"] = {"fs_live_gl_posting": False}
		try:
			out = post_fs_scenario_gl(
				company=company,
				scenario="loan_disbursement",
				principal="1000",
			)
			self.assertFalse(out["posted"])
			self.assertIn("lines", out)
		finally:
			if old is None:
				frappe.local.conf.pop("omnexa_feature_flags", None)
			else:
				frappe.local.conf["omnexa_feature_flags"] = old

	def test_vertical_leasing_preview_path(self):
		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No company")
		out = post_fs_scenario_gl(
			company=company,
			scenario="lease_recognition",
			vertical="leasing",
			rou_asset="100",
			lease_liability="100",
		)
		self.assertFalse(out["posted"])
