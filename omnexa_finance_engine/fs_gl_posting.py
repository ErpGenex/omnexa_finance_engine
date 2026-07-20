# Copyright (c) 2026, ErpGenEx
"""FS scenario → live JE (via omnexa_accounting, feature-flag gated)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from omnexa_finance_engine.fs_parity_bridge import preview_gl_for_vertical
from omnexa_finance_engine.fs_posting_matrix import (
	preview_early_termination_posting,
	preview_lease_recognition_posting,
	preview_loan_disbursement_posting,
)


def _matrix_for_scenario(scenario: str, **amounts: str) -> list[dict]:
	scenario = (scenario or "").strip().lower()
	if scenario == "lease_recognition":
		return preview_lease_recognition_posting(
			Decimal(str(amounts.get("rou_asset", "0"))),
			Decimal(str(amounts.get("lease_liability", "0"))),
		)
	if scenario == "early_termination":
		return preview_early_termination_posting(
			Decimal(str(amounts.get("settlement_cash", "0"))),
			Decimal(str(amounts.get("lease_liability", "0"))),
			Decimal(str(amounts.get("rou_asset", "0"))),
		)
	return preview_loan_disbursement_posting(Decimal(str(amounts.get("principal", "0"))))


def post_fs_scenario_gl(
	*,
	company: str,
	scenario: str,
	vertical: str | None = None,
	branch: str | None = None,
	posting_date: str | None = None,
	rou_asset: str = "0",
	lease_liability: str = "0",
	principal: str = "0",
	settlement_cash: str = "0",
) -> dict[str, Any]:
	"""Preview + optional JE when ``fs_live_gl_posting`` is enabled."""
	if vertical:
		preview = preview_gl_for_vertical(
			vertical,
			scenario=scenario,
			rou_asset=rou_asset,
			lease_liability=lease_liability,
			principal=principal,
			settlement_cash=settlement_cash,
		)
		lines = preview["lines"]
		scenario = preview["scenario"]
	else:
		lines = _matrix_for_scenario(
			scenario,
			rou_asset=rou_asset,
			lease_liability=lease_liability,
			principal=principal,
			settlement_cash=settlement_cash,
		)

	from omnexa_accounting.utils.fs_matrix_posting import post_fs_matrix_gl

	ref = f"FS:{vertical or 'engine'}:{scenario}"
	return post_fs_matrix_gl(
		company=company,
		scenario=scenario,
		matrix_lines=lines,
		posting_date=posting_date,
		branch=branch,
		reference=ref,
		remarks=f"FS {vertical or 'engine'} — {scenario}",
	)
