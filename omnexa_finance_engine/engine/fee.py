# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .money import Money


FeeType = str  # FIXED | PERCENT


@dataclass(frozen=True)
class FeeRule:
	"""
	Simple fee rule primitive for schedule preview.

	- FIXED: amount in loan currency.
	- PERCENT: percentage of opening principal (0.01 = 1%).
	- applies_each_period: when False, applies only on first period.
	"""

	fee_type: FeeType
	value: Decimal
	applies_each_period: bool = True
	min_amount: Decimal | None = None
	max_amount: Decimal | None = None


def calculate_period_fee(rule: FeeRule | None, opening_principal: Money, period: int, periods: int) -> Money:
	if not rule:
		return Money(Decimal("0"), opening_principal.currency, opening_principal.rounding)
	if not rule.applies_each_period and period > 1:
		return Money(Decimal("0"), opening_principal.currency, opening_principal.rounding)

	if rule.fee_type == "FIXED":
		raw = rule.value
	elif rule.fee_type == "PERCENT":
		raw = opening_principal.amount * rule.value
	else:
		raise ValueError(f"Unsupported fee_type: {rule.fee_type}")

	if rule.min_amount is not None:
		raw = max(raw, rule.min_amount)
	if rule.max_amount is not None:
		raw = min(raw, rule.max_amount)

	return Money(raw, opening_principal.currency, opening_principal.rounding).rounded()

