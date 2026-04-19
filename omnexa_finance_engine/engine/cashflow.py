# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import isfinite


@dataclass(frozen=True)
class CashflowPoint:
	when: date
	amount: Decimal  # outflow negative, inflow positive


def npv(flows: list[CashflowPoint], rate: float) -> float:
	if not flows:
		return 0.0
	t0 = flows[0].when
	total = 0.0
	for f in flows:
		days = (f.when - t0).days
		total += float(f.amount) / ((1.0 + rate) ** (days / 365.0))
	return total


def xirr(flows: list[CashflowPoint], *, guess: float = 0.12) -> float:
	"""
	Compute IRR using actual dates (XIRR), Newton-Raphson with fallback bisection.
	Raises ValueError when sign conditions are not met.
	"""
	_validate_flows(flows)

	r = guess
	for _ in range(50):
		f = npv(flows, r)
		df = _d_npv(flows, r)
		if abs(f) < 1e-8:
			return r
		if abs(df) < 1e-12:
			break
		nr = r - f / df
		if not isfinite(nr) or nr <= -0.999999:
			break
		r = nr

	# Fallback robust bisection
	low, high = -0.95, 5.0
	f_low = npv(flows, low)
	f_high = npv(flows, high)
	if f_low == 0:
		return low
	if f_high == 0:
		return high
	if f_low * f_high > 0:
		raise ValueError("Unable to bracket XIRR root")
	for _ in range(100):
		mid = (low + high) / 2
		f_mid = npv(flows, mid)
		if abs(f_mid) < 1e-8:
			return mid
		if f_low * f_mid < 0:
			high, f_high = mid, f_mid
		else:
			low, f_low = mid, f_mid
	return (low + high) / 2


def build_loan_cashflows(principal: Decimal, disbursement_date: date, due_lines: list[dict]) -> list[CashflowPoint]:
	"""Build borrower-facing cashflows from disbursement and schedule totals."""
	flows = [CashflowPoint(when=disbursement_date, amount=-principal)]
	for ln in due_lines:
		flows.append(CashflowPoint(when=date.fromisoformat(str(ln["due_date"])), amount=Decimal(str(ln["total_due"]))))
	return flows


def _d_npv(flows: list[CashflowPoint], rate: float) -> float:
	t0 = flows[0].when
	total = 0.0
	for f in flows:
		t = (f.when - t0).days / 365.0
		total += -t * float(f.amount) / ((1.0 + rate) ** (t + 1.0))
	return total


def _validate_flows(flows: list[CashflowPoint]) -> None:
	if len(flows) < 2:
		raise ValueError("At least two cashflows are required")
	has_pos = any(f.amount > 0 for f in flows)
	has_neg = any(f.amount < 0 for f in flows)
	if not (has_pos and has_neg):
		raise ValueError("Cashflows must include both positive and negative amounts")

