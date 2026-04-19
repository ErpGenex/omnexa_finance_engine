# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from datetime import date
from decimal import Decimal

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.engine import (
	CurrencyRounding,
	DayCountConvention,
	FeeRule,
	InterestRate,
	Money,
	ScheduleInput,
	build_schedule,
)


class TestScheduleEngine(FrappeTestCase):
	def test_annuity_schedule_closes_principal(self):
		inp = ScheduleInput(
			principal=Money(Decimal("10000"), "USD", CurrencyRounding(2, "HALF_UP")),
			start_date=date(2026, 1, 1),
			first_due_date=date(2026, 2, 1),
			periods=12,
			rate=InterestRate(annual_rate=Decimal("0.12")),
			day_count=DayCountConvention("ACT_365F"),
			amortization="ANNUITY",
		)
		lines = build_schedule(inp)
		self.assertEqual(len(lines), 12)
		self.assertEqual(lines[-1].closing_principal.amount, Decimal("0.00"))

	def test_equal_principal_schedule_closes_principal(self):
		inp = ScheduleInput(
			principal=Money(Decimal("1200"), "USD", CurrencyRounding(2, "HALF_UP")),
			start_date=date(2026, 1, 1),
			first_due_date=date(2026, 2, 1),
			periods=12,
			rate=InterestRate(annual_rate=Decimal("0.00")),
			day_count=DayCountConvention("ACT_365F"),
			amortization="EQUAL_PRINCIPAL",
		)
		lines = build_schedule(inp)
		self.assertEqual(lines[-1].closing_principal.amount, Decimal("0.00"))

	def test_principal_grace_periods(self):
		inp = ScheduleInput(
			principal=Money(Decimal("10000"), "USD", CurrencyRounding(2, "HALF_UP")),
			start_date=date(2026, 1, 1),
			first_due_date=date(2026, 2, 1),
			periods=6,
			rate=InterestRate(annual_rate=Decimal("0.12")),
			day_count=DayCountConvention("ACT_365F"),
			amortization="EQUAL_PRINCIPAL",
			principal_grace_periods=2,
		)
		lines = build_schedule(inp)
		self.assertEqual(lines[0].principal.amount, Decimal("0.00"))
		self.assertEqual(lines[1].principal.amount, Decimal("0.00"))
		self.assertEqual(lines[-1].closing_principal.amount, Decimal("0.00"))

	def test_monthly_due_date_rollover_and_fee(self):
		inp = ScheduleInput(
			principal=Money(Decimal("3000"), "USD", CurrencyRounding(2, "HALF_UP")),
			start_date=date(2026, 1, 31),
			first_due_date=date(2026, 2, 28),
			periods=3,
			rate=InterestRate(annual_rate=Decimal("0.00")),
			day_count=DayCountConvention("ACT_365F"),
			amortization="EQUAL_PRINCIPAL",
			fee_rule=FeeRule(fee_type="FIXED", value=Decimal("10.00"), applies_each_period=True),
		)
		lines = build_schedule(inp)
		self.assertEqual(lines[0].due_date.isoformat(), "2026-02-28")
		self.assertEqual(lines[1].due_date.isoformat(), "2026-03-28")
		self.assertEqual(lines[2].due_date.isoformat(), "2026-04-28")
		self.assertEqual(lines[0].fees.amount, Decimal("10.00"))

