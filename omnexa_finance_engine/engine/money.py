# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN


@dataclass(frozen=True)
class CurrencyRounding:
	"""Defines rounding policy for a currency (precision + mode)."""

	precision: int = 2
	mode: str = "HALF_UP"  # HALF_UP | HALF_EVEN

	def quantize(self, amount: Decimal) -> Decimal:
		q = Decimal(10) ** (-self.precision)
		rounding = ROUND_HALF_UP if self.mode == "HALF_UP" else ROUND_HALF_EVEN
		return amount.quantize(q, rounding=rounding)


@dataclass(frozen=True)
class Money:
	amount: Decimal
	currency: str
	rounding: CurrencyRounding = CurrencyRounding()

	def rounded(self) -> "Money":
		return Money(self.rounding.quantize(self.amount), self.currency, self.rounding)

	def __add__(self, other: "Money") -> "Money":
		if self.currency != other.currency:
			raise ValueError("Currency mismatch")
		return Money(self.amount + other.amount, self.currency, self.rounding)

	def __sub__(self, other: "Money") -> "Money":
		if self.currency != other.currency:
			raise ValueError("Currency mismatch")
		return Money(self.amount - other.amount, self.currency, self.rounding)


@dataclass(frozen=True)
class FXQuote:
	source_currency: str
	target_currency: str
	rate: Decimal


def convert_money(
	amount: Money,
	target_currency: str,
	quote: FXQuote,
	target_rounding: CurrencyRounding | None = None,
) -> Money:
	"""
	Convert money using explicit source->target quote.
	Example: 100 USD with USD->EUR rate 0.92 => 92 EUR.
	"""
	if amount.currency != quote.source_currency:
		raise ValueError("FX quote source does not match amount currency")
	if str(target_currency) != quote.target_currency:
		raise ValueError("FX quote target does not match requested target currency")
	if quote.rate <= 0:
		raise ValueError("FX rate must be positive")

	rounding = target_rounding or amount.rounding
	converted = rounding.quantize(amount.amount * quote.rate)
	return Money(amount=converted, currency=quote.target_currency, rounding=rounding)

