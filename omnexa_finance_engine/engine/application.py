from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import frappe

from .day_count import DayCountConvention
from .fee import FeeRule
from .money import CurrencyRounding, Money
from .rates import InterestRate
from .schedule import ScheduleInput, build_schedule


@dataclass(frozen=True)
class QuoteRequest:
	principal: Decimal
	currency: str
	annual_rate: Decimal
	start_date: date
	first_due_date: date
	periods: int
	amortization: str
	payment_frequency: str
	day_count: str = "ACT_365F"
	principal_grace_periods: int = 0
	fee_type: str | None = None
	fee_value: Decimal | None = None
	fee_applies_each_period: bool = True


def build_quote(req: QuoteRequest) -> dict:
	fee_rule = None
	if req.fee_type and req.fee_value is not None:
		fee_rule = FeeRule(
			fee_type=req.fee_type,
			value=req.fee_value,
			applies_each_period=req.fee_applies_each_period,
		)

	schedule_input = ScheduleInput(
		principal=Money(req.principal, req.currency, CurrencyRounding(2, "HALF_UP")),
		start_date=req.start_date,
		first_due_date=req.first_due_date,
		periods=req.periods,
		rate=InterestRate(annual_rate=req.annual_rate),
		day_count=DayCountConvention(req.day_count),
		amortization=req.amortization,
		payment_frequency=req.payment_frequency,
		principal_grace_periods=req.principal_grace_periods,
		fee_rule=fee_rule,
	)
	lines = build_schedule(schedule_input)
	total_interest = sum((ln.interest.amount for ln in lines), Decimal("0"))
	total_fees = sum((ln.fees.amount for ln in lines), Decimal("0"))
	total_principal = sum((ln.principal.amount for ln in lines), Decimal("0"))
	total_due = sum((ln.total_due.amount for ln in lines), Decimal("0"))

	return {
		"currency": req.currency,
		"totals": {
			"principal": str(total_principal),
			"interest": str(total_interest),
			"fees": str(total_fees),
			"total_due": str(total_due),
		},
		"lines": [
			{
				"period": ln.period,
				"due_date": ln.due_date.isoformat(),
				"opening_principal": str(ln.opening_principal.amount),
				"interest": str(ln.interest.amount),
				"principal": str(ln.principal.amount),
				"fees": str(ln.fees.amount),
				"total_due": str(ln.total_due.amount),
				"closing_principal": str(ln.closing_principal.amount),
			}
			for ln in lines
		],
	}


def make_explainability(req: QuoteRequest, quote_out: dict, event_type: str = "QUOTE") -> dict:
	return {
		"event_type": event_type,
		"policy_basis": {"interest_method": req.amortization, "day_count": req.day_count},
		"inputs": {
			"principal": str(req.principal),
			"currency": req.currency,
			"annual_rate": str(req.annual_rate),
			"periods": req.periods,
			"payment_frequency": req.payment_frequency,
		},
		"totals": quote_out.get("totals", {}),
		"reason_codes": ["BASE_PRODUCT_POLICY", "IFRS_GAAP_CALC_TRACE_ENABLED"],
	}


def payload_hash(payload: dict) -> str:
	def _norm(v):
		if isinstance(v, Decimal):
			return str(v)
		if isinstance(v, date):
			return v.isoformat()
		if isinstance(v, dict):
			return {k: _norm(x) for k, x in v.items()}
		if isinstance(v, (list, tuple)):
			return [_norm(x) for x in v]
		return v

	serial = json.dumps(_norm(payload), sort_keys=True, separators=(",", ":"))
	return hashlib.sha256(serial.encode("utf-8")).hexdigest()


def get_cached_idempotent_result(namespace: str, idempotency_key: str) -> dict | None:
	raw = frappe.cache().hget("finance_engine_idempotency", f"{namespace}:{idempotency_key}")
	if not raw:
		return None
	try:
		return json.loads(raw)
	except Exception:
		return None


def set_cached_idempotent_result(namespace: str, idempotency_key: str, payload: dict) -> None:
	frappe.cache().hset(
		"finance_engine_idempotency",
		f"{namespace}:{idempotency_key}",
		json.dumps(payload, sort_keys=True, separators=(",", ":")),
	)
