# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.api import preview_schedule, preview_schedule_with_metrics


class TestPreviewScheduleApi(FrappeTestCase):
	def test_preview_schedule_minimal(self):
		out = preview_schedule(
			principal="1200",
			currency="USD",
			annual_rate="0.12",
			start_date="2026-01-01",
			first_due_date="2026-02-01",
			periods=12,
		)
		self.assertEqual(out["currency"], "USD")
		self.assertEqual(len(out["lines"]), 12)
		self.assertIn("total_due", out["lines"][0])

	def test_preview_schedule_with_metrics(self):
		out = preview_schedule_with_metrics(
			principal="1200",
			currency="USD",
			annual_rate="0.12",
			start_date="2026-01-01",
			first_due_date="2026-02-01",
			periods=12,
		)
		self.assertIn("metrics", out)
		self.assertIn("xirr", out["metrics"])

