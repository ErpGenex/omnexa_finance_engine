# Copyright (c) 2026, ErpGenEx
import frappe
from frappe.tests.utils import FrappeTestCase


class TestSapParityFinanceSector(FrappeTestCase):
	def test_gap_register_module_importable(self):
		self.assertTrue(bool(frappe.get_module("omnexa_finance_engine.fe_gap_register")))
