# Copyright (c) 2026, Omnexa and contributors

from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.exceptions import ValidationError

from omnexa_finance_engine.api import (
	approve_finance_product_status_change,
	create_finance_contract,
	list_finance_accounting_templates,
	list_schedule_versions,
	record_schedule_snapshot_for_contract,
	replay_finance_calc_run,
	submit_finance_product_status_change,
)


class TestFinanceEngineWave3(FrappeTestCase):
	def _currency(self) -> str:
		if frappe.db.exists("Currency", "USD"):
			return "USD"
		choices = frappe.get_all("Currency", pluck="name", limit=1)
		return choices[0] if choices else "USD"

	def _ensure_user(self, email: str) -> None:
		if frappe.db.exists("User", email):
			return
		doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Checker",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		)
		doc.append("roles", {"role": "System Manager"})
		doc.insert(ignore_permissions=True)

	def _active_product(self) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Finance Product",
				"product_name": "Wave3 Test Product",
				"product_code": f"W3-{frappe.generate_hash(length=8)}",
				"status": "ACTIVE",
				"company_code": "CO1",
				"branch_code": "BR1",
				"currency": self._currency(),
				"interest_method": "ANNUITY",
				"default_annual_rate": 0.12,
				"default_periods": 12,
				"payment_frequency": "MONTHLY",
				"day_count": "ACT_365F",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_product_status_maker_checker_and_contract_requires_active(self):
		currency = self._currency()
		doc = frappe.get_doc(
			{
				"doctype": "Finance Product",
				"product_name": "Draft Only",
				"product_code": f"DR-{frappe.generate_hash(length=8)}",
				"status": "DRAFT",
				"currency": currency,
				"interest_method": "ANNUITY",
				"default_annual_rate": 0.1,
				"default_periods": 12,
				"payment_frequency": "MONTHLY",
				"day_count": "ACT_365F",
			}
		)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(ValidationError):
			create_finance_contract(
				product=doc.name,
				customer_name="X",
				principal="1000",
				currency=currency,
				annual_rate="0.1",
				start_date="2026-01-01",
				first_due_date="2026-02-01",
				periods=6,
			)

		active = self._active_product()
		submit_finance_product_status_change(active, "SUSPENDED")
		self.assertEqual(frappe.db.get_value("Finance Product", active, "pending_status"), "SUSPENDED")
		self._ensure_user("checker_wave3_finance@example.com")
		frappe.set_user("checker_wave3_finance@example.com")
		approve_finance_product_status_change(active)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Finance Product", active, "status"), "SUSPENDED")

	def test_schedule_snapshot_versioning_and_replay(self):
		currency = self._currency()
		product = self._active_product()
		out = create_finance_contract(
			product=product,
			customer_name="Snap Customer",
			principal="50000",
			currency=currency,
			annual_rate="0.09",
			start_date="2026-01-01",
			first_due_date="2026-02-01",
			periods=12,
			company_code="CO1",
			branch_code="BR1",
		)
		ca = out["contract_account"]
		snap = record_schedule_snapshot_for_contract(ca)
		self.assertEqual(snap["schedule_version"], 1)
		rows = list_schedule_versions(ca)
		self.assertGreaterEqual(len(rows), 1)
		replay = replay_finance_calc_run(snap["calc_run"])
		self.assertTrue(replay["outputs_identical"])

	def test_accounting_event_template_list(self):
		frappe.get_doc(
			{
				"doctype": "Finance Accounting Event Template",
				"template_code": f"ACC-{frappe.generate_hash(length=6)}",
				"title": "Test Accrual",
				"event_type": "ACCRUAL",
				"status": "ACTIVE",
				"debit_account_hint": "LOANS_RECEIVABLE",
				"credit_account_hint": "INTEREST_INCOME",
			}
		).insert(ignore_permissions=True)
		templates = list_finance_accounting_templates(event_type="ACCRUAL")
		self.assertTrue(any(t.get("event_type") == "ACCRUAL" for t in templates))
