# Copyright (c) 2026, ErpGenEx
"""Shared GL posting preview bridge for FS vertical apps (Wave B)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from omnexa_finance_engine.fs_posting_matrix import (
	preview_early_termination_posting,
	preview_lease_recognition_posting,
	preview_loan_disbursement_posting,
)

VERTICAL_DEFAULTS: dict[str, str] = {
	"leasing": "lease_recognition",
	"mortgage": "loan_disbursement",
	"vehicle": "loan_disbursement",
	"consumer": "loan_disbursement",
	"factoring": "loan_disbursement",
	"sme_retail": "loan_disbursement",
	"credit_engine": "loan_disbursement",
	"credit_risk": "loan_disbursement",
	"alm": "loan_disbursement"
	}


def preview_gl_for_vertical(
	vertical: str,
	scenario: str | None = None,
	*,
	rou_asset: str = "0",
	lease_liability: str = "0",
	principal: str = "0",
	settlement_cash: str = "0",
) -> dict[str, Any]:
	"""Route vertical app → posting matrix preview (no JE)."""
	vertical = (vertical or "").strip().lower()
	scenario = (scenario or VERTICAL_DEFAULTS.get(vertical) or "loan_disbursement").strip().lower()

	if scenario == "lease_recognition":
		lines = preview_lease_recognition_posting(
			Decimal(str(rou_asset)), Decimal(str(lease_liability))
		)
	elif scenario == "loan_disbursement":
		lines = preview_loan_disbursement_posting(Decimal(str(principal)))
	elif scenario == "early_termination":
		lines = preview_early_termination_posting(
			Decimal(str(settlement_cash)),
			Decimal(str(lease_liability)),
			Decimal(str(rou_asset)),
		)
	else:
		lines = preview_loan_disbursement_posting(Decimal(str(principal)))

	return {"vertical": vertical, "scenario": scenario, "lines": lines
	}
