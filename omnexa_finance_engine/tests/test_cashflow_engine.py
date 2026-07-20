# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from datetime import date
from decimal import Decimal

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.engine.cashflow import CashflowPoint, npv, xirr


class TestCashflowEngine(FrappeTestCase):
	def test_xirr_basic_loan_like_flow(self):
		flows = [
			CashflowPoint(date(2026, 1, 1), Decimal("-1000")),
			CashflowPoint(date(2026, 7, 1), Decimal("550")),
			CashflowPoint(date(2027, 1, 1), Decimal("550")),
		]
		r = xirr(flows)
		self.assertGreater(r, 0.13)
		self.assertLess(r, 0.15)

	def test_npv_zero_near_xirr(self):
		flows = [
			CashflowPoint(date(2026, 1, 1), Decimal("-1000")),
			CashflowPoint(date(2026, 7, 1), Decimal("550")),
			CashflowPoint(date(2027, 1, 1), Decimal("550")),
		]
		r = xirr(flows)
		self.assertAlmostEqual(npv(flows, r), 0.0, places=6)

