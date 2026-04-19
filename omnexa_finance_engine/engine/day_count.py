# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DayCountConvention:
	"""
	Day count conventions for interest accrual.

	Supported:
	- ACT_360
	- ACT_365F
	- THIRTY_360_US
	"""

	name: str

	def year_fraction(self, start: date, end: date) -> float:
		if end <= start:
			return 0.0

		if self.name == "ACT_360":
			return (end - start).days / 360.0
		if self.name == "ACT_365F":
			return (end - start).days / 365.0
		if self.name == "THIRTY_360_US":
			return _year_fraction_30_360_us(start, end)

		raise ValueError(f"Unsupported day count: {self.name}")


def _year_fraction_30_360_us(start: date, end: date) -> float:
	# US 30/360 (NASD) simplified implementation.
	d1 = min(start.day, 30)
	d2 = end.day
	if start.day in (30, 31) and end.day == 31:
		d2 = 30
	days = (end.year - start.year) * 360 + (end.month - start.month) * 30 + (d2 - d1)
	return days / 360.0

