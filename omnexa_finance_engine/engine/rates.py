# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


Compounding = str  # SIMPLE | MONTHLY | DAILY
RateBasis = str  # NOMINAL | EFFECTIVE


@dataclass(frozen=True)
class InterestRate:
	annual_rate: Decimal  # e.g. 0.12 for 12%
	compounding: Compounding = "SIMPLE"
	basis: RateBasis = "NOMINAL"

	def periodic_rate(self, periods_per_year: int) -> Decimal:
		if periods_per_year <= 0:
			raise ValueError("periods_per_year must be > 0")
		if self.compounding == "SIMPLE":
			return self.annual_rate / Decimal(periods_per_year)
		if self.compounding == "MONTHLY":
			return self.annual_rate / Decimal(12)
		if self.compounding == "DAILY":
			return self.annual_rate / Decimal(365)
		raise ValueError(f"Unsupported compounding: {self.compounding}")

