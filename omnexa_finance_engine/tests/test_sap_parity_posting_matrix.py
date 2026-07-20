# Copyright (c) 2026, ErpGenEx
from decimal import Decimal

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.fs_posting_matrix import (
	preview_lease_recognition_posting,
	preview_loan_disbursement_posting,
)


class TestSapParityPostingMatrix(FrappeTestCase):
	def test_lease_recognition_balanced_roles(self):
		lines = preview_lease_recognition_posting(Decimal("100"), Decimal("100"))
		self.assertEqual(len(lines), 2)
		debit = sum(Decimal(l["debit"]) for l in lines)
		credit = sum(Decimal(l["credit"]) for l in lines)
		self.assertEqual(debit, credit)

	def test_loan_disbursement_balanced(self):
		lines = preview_loan_disbursement_posting(Decimal("50000"))
		debit = sum(Decimal(l["debit"]) for l in lines)
		credit = sum(Decimal(l["credit"]) for l in lines)
		self.assertEqual(debit, credit)
