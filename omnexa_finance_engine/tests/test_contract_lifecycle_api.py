from frappe.tests.utils import FrappeTestCase
import frappe

from omnexa_finance_engine.api import (
	create_finance_contract,
	get_calc_run_explainability,
	list_finance_outbox_events,
	quote_finance_product,
	recalculate_finance_contract,
	simulate_finance_contract_scenario,
)


class TestFinanceContractLifecycleApi(FrappeTestCase):
	def _currency(self) -> str:
		if frappe.db.exists("Currency", "USD"):
			return "USD"
		choices = frappe.get_all("Currency", pluck="name", limit=1)
		return choices[0] if choices else "USD"

	def _create_product(self) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Finance Product",
				"product_name": "Test Personal Loan",
				"product_code": f"TST-{frappe.generate_hash(length=8)}",
				"status": "ACTIVE",
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

	def test_quote_create_recalculate_and_explainability(self):
		currency = self._currency()
		product = self._create_product()
		quote = quote_finance_product(
			principal="100000",
			currency=currency,
			annual_rate="0.14",
			start_date="2026-01-01",
			first_due_date="2026-02-01",
			periods=12,
			idempotency_key="tst-finance-quote-1",
		)
		self.assertIn("quote", quote)
		self.assertIn("calc_run", quote)
		self.assertTrue(quote["quote"]["lines"])

		contract_out = create_finance_contract(
			product=product,
			customer_name="Lifecycle Test Customer",
			principal="100000",
			currency=currency,
			annual_rate="0.14",
			start_date="2026-01-01",
			first_due_date="2026-02-01",
			periods=12,
			idempotency_key="tst-finance-contract-1",
		)
		self.assertIn("contract_account", contract_out)
		self.assertIn("calc_run", contract_out)

		recalc = recalculate_finance_contract(
			contract_account=contract_out["contract_account"],
			event_type="RESTRUCTURE",
			override_annual_rate="0.10",
			idempotency_key="tst-finance-recalc-1",
		)
		self.assertEqual(recalc["contract_account"], contract_out["contract_account"])
		self.assertIn("calc_run", recalc)

		explain_rows = get_calc_run_explainability(contract_account=contract_out["contract_account"], limit=5)
		self.assertGreaterEqual(len(explain_rows), 1)
		self.assertIn("explainability", explain_rows[0])

		scenario = simulate_finance_contract_scenario(
			contract_account=contract_out["contract_account"],
			scenario_name="stress-200bps",
			rate_shift_bps=200,
			fee_multiplier="1.2",
			fx_rate_override="1.05",
			idempotency_key="tst-finance-scenario-1",
		)
		self.assertIn("scenario_run", scenario)
		self.assertIn("quote", scenario)
		self.assertIn("explainability", scenario)

		recalc_settlement = recalculate_finance_contract(
			contract_account=contract_out["contract_account"],
			event_type="EARLY_SETTLEMENT",
			idempotency_key="tst-finance-settlement-1",
		)
		self.assertEqual(recalc_settlement["contract_account"], contract_out["contract_account"])

		outbox = list_finance_outbox_events(limit=20)
		self.assertGreaterEqual(len(outbox), 1)
		self.assertIn("event_type", outbox[0])
