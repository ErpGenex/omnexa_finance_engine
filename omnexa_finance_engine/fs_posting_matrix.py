# Copyright (c) 2026, ErpGenEx
"""FS → GL posting matrix preview (SAP FS-CML / FI-GL bridge) — no side effects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PostingLine:
	account_role: str
	debit: Decimal
	credit: Decimal
	remarks: str = ""

	def to_dict(self) -> dict[str, Any]:
		return {
			"account_role": self.account_role,
			"debit": str(self.debit),
			"credit": str(self.credit),
			"remarks": self.remarks
	}


def preview_lease_recognition_posting(
	rou_asset: Decimal,
	lease_liability: Decimal,
	*,
	company: str = "",
) -> list[dict]:
	"""IFRS 16 initial recognition (preview only)."""
	rou = max(Decimal("0"), rou_asset)
	liab = max(Decimal("0"), lease_liability)
	return [
		PostingLine("rou_asset", rou, Decimal("0"), "IFRS16 ROU").to_dict(),
		PostingLine("lease_liability", Decimal("0"), liab, "IFRS16 liability").to_dict(),
	]


def preview_loan_disbursement_posting(
	principal: Decimal,
	cash_account_role: str = "bank",
	loan_receivable_role: str = "loan_receivable",
) -> list[dict]:
	principal = max(Decimal("0"), principal)
	return [
		PostingLine(loan_receivable_role, principal, Decimal("0"), "Disbursement").to_dict(),
		PostingLine(cash_account_role, Decimal("0"), principal, "Cash out").to_dict(),
	]


def preview_early_termination_posting(
	settlement_cash: Decimal,
	liability_clear: Decimal,
	rou_clear: Decimal,
	pl_role: str = "termination_pl",
) -> list[dict]:
	return [
		PostingLine("lease_liability", liability_clear, Decimal("0"), "Clear liability").to_dict(),
		PostingLine("rou_asset", Decimal("0"), rou_clear, "Derecognize ROU").to_dict(),
		PostingLine("bank", settlement_cash, Decimal("0"), "Settlement cash").to_dict(),
		PostingLine(pl_role, Decimal("0"), max(Decimal("0"), settlement_cash - liability_clear), "P&L").to_dict(),
	]
