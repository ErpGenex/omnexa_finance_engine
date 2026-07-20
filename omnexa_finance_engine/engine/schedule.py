# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .day_count import DayCountConvention
from .fee import FeeRule, calculate_period_fee
from .money import Money
from .rates import InterestRate


AmortizationMethod = str  # ANNUITY | EQUAL_PRINCIPAL
PaymentFrequency = str  # MONTHLY | WEEKLY | FORTNIGHTLY | DAILY


@dataclass(frozen=True)
class ScheduleInput:
	principal: Money
	start_date: date
	first_due_date: date
	periods: int
	rate: InterestRate
	day_count: DayCountConvention
	payment_frequency: PaymentFrequency = "MONTHLY"
	period_days: int | None = None  # used only with DAILY custom cadence
	amortization: AmortizationMethod = "ANNUITY"
	principal_grace_periods: int = 0
	fee_rule: FeeRule | None = None


@dataclass(frozen=True)
class ScheduleLine:
	period: int
	due_date: date
	opening_principal: Money
	interest: Money
	principal: Money
	fees: Money
	closing_principal: Money
	total_due: Money


def build_schedule(inp: ScheduleInput) -> list[ScheduleLine]:
	if inp.periods <= 0:
		raise ValueError("periods must be > 0")
	if inp.first_due_date <= inp.start_date:
		raise ValueError("first_due_date must be after start_date")
	if inp.principal_grace_periods < 0 or inp.principal_grace_periods >= inp.periods:
		raise ValueError("principal_grace_periods must be >= 0 and < periods")

	cur_open = inp.principal.rounded()
	due = inp.first_due_date

	lines: list[ScheduleLine] = []
	if inp.amortization == "ANNUITY":
		pmt = _annuity_payment(inp)
		for i in range(1, inp.periods + 1):
			prev_due = inp.start_date if i == 1 else lines[-1].due_date
			int_amt = _interest_for_period(cur_open, prev_due, due, inp.rate, inp.day_count)
			fee_amt = calculate_period_fee(inp.fee_rule, cur_open, i, inp.periods)
			is_grace = i <= inp.principal_grace_periods
			if is_grace:
				prn_amt = Money(Decimal("0"), inp.principal.currency, inp.principal.rounding)
				total_due = Money(int_amt.amount + fee_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
			else:
				prn_amt = Money(pmt.amount - int_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
				total_due = Money(prn_amt.amount + int_amt.amount + fee_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
			if i == inp.periods and not is_grace:
				# final period: close fully (avoid rounding residuals)
				prn_amt = cur_open.rounded()
				total_due = Money(prn_amt.amount + int_amt.amount + fee_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
			cur_close = Money(cur_open.amount - prn_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
			lines.append(
				ScheduleLine(
					period=i,
					due_date=due,
					opening_principal=cur_open,
					interest=int_amt,
					principal=prn_amt,
					fees=fee_amt,
					closing_principal=cur_close,
					total_due=total_due,
				)
			)
			cur_open = cur_close
			due = _next_due_date(due, inp)
		return lines

	if inp.amortization == "EQUAL_PRINCIPAL":
		amort_periods = inp.periods - inp.principal_grace_periods
		each = Money(inp.principal.amount / Decimal(amort_periods), inp.principal.currency, inp.principal.rounding).rounded()
		for i in range(1, inp.periods + 1):
			prev_due = inp.start_date if i == 1 else lines[-1].due_date
			int_amt = _interest_for_period(cur_open, prev_due, due, inp.rate, inp.day_count)
			fee_amt = calculate_period_fee(inp.fee_rule, cur_open, i, inp.periods)
			is_grace = i <= inp.principal_grace_periods
			prn_amt = Money(Decimal("0"), inp.principal.currency, inp.principal.rounding) if is_grace else each
			if i == inp.periods and not is_grace:
				prn_amt = cur_open.rounded()
			pmt = Money(prn_amt.amount + int_amt.amount + fee_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
			cur_close = Money(cur_open.amount - prn_amt.amount, inp.principal.currency, inp.principal.rounding).rounded()
			lines.append(
				ScheduleLine(
					period=i,
					due_date=due,
					opening_principal=cur_open,
					interest=int_amt,
					principal=prn_amt,
					fees=fee_amt,
					closing_principal=cur_close,
					total_due=pmt,
				)
			)
			cur_open = cur_close
			due = _next_due_date(due, inp)
		return lines

	raise ValueError(f"Unsupported amortization method: {inp.amortization}")


def _interest_for_period(
	opening: Money, start: date, end: date, rate: InterestRate, day_count: DayCountConvention
) -> Money:
	yf = Decimal(str(day_count.year_fraction(start, end)))
	int_amt = (opening.amount * rate.annual_rate * yf)
	return Money(int_amt, opening.currency, opening.rounding).rounded()


def _annuity_payment(inp: ScheduleInput) -> Money:
	# Use first period as representative for the periodic rate.
	yf = Decimal(str(inp.day_count.year_fraction(inp.start_date, inp.first_due_date)))
	r = inp.rate.annual_rate * yf
	amort_periods = inp.periods - inp.principal_grace_periods
	if r == 0:
		return Money(inp.principal.amount / Decimal(amort_periods), inp.principal.currency, inp.principal.rounding).rounded()
	n = Decimal(amort_periods)
	one = Decimal(1)
	pmt = inp.principal.amount * (r / (one - (one + r) ** (-n)))
	return Money(pmt, inp.principal.currency, inp.principal.rounding).rounded()


def _next_due_date(current_due: date, inp: ScheduleInput) -> date:
	if inp.payment_frequency == "MONTHLY":
		return _add_months(current_due, 1)
	if inp.payment_frequency == "WEEKLY":
		return current_due + timedelta(days=7)
	if inp.payment_frequency == "FORTNIGHTLY":
		return current_due + timedelta(days=14)
	if inp.payment_frequency == "DAILY":
		step = inp.period_days or 1
		if step <= 0:
			raise ValueError("period_days must be > 0 for DAILY frequency")
		return current_due + timedelta(days=step)
	raise ValueError(f"Unsupported payment_frequency: {inp.payment_frequency}")


def _add_months(base: date, months: int) -> date:
	total_month = base.month - 1 + months
	year = base.year + total_month // 12
	month = total_month % 12 + 1
	day = min(base.day, _days_in_month(year, month))
	return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
	if month == 2:
		leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
		return 29 if leap else 28
	if month in (4, 6, 9, 11):
		return 30
	return 31

