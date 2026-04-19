# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
import json

import frappe

from omnexa_finance_engine.standards_profile import get_standards_profile as _get_standards_profile
from omnexa_finance_engine.engine import (
	build_loan_cashflows,
	CurrencyRounding,
	DayCountConvention,
	FeeRule,
	FXQuote,
	InterestRate,
	Money,
	ScheduleInput,
	build_schedule,
	convert_money,
	QuoteRequest,
	build_quote,
	make_explainability,
	payload_hash,
	get_cached_idempotent_result,
	set_cached_idempotent_result,
	xirr,
)


def _to_date(value: str) -> date:
	return date.fromisoformat(str(value))


@frappe.whitelist()
def preview_schedule(
	principal: str,
	currency: str,
	annual_rate: str,
	start_date: str,
	first_due_date: str,
	periods: int = 12,
	day_count: str = "ACT_365F",
	amortization: str = "ANNUITY",
	payment_frequency: str = "MONTHLY",
	principal_grace_periods: int = 0,
	fee_type: str | None = None,
	fee_value: str | None = None,
	fee_applies_each_period: int = 1,
) -> dict:
	"""Public schedule preview API for consumer/vehicle/mortgage apps."""
	fee_rule = None
	if fee_type and fee_value is not None:
		fee_rule = FeeRule(
			fee_type=str(fee_type),
			value=Decimal(str(fee_value)),
			applies_each_period=bool(int(fee_applies_each_period)),
		)

	inp = ScheduleInput(
		principal=Money(Decimal(str(principal)), str(currency), CurrencyRounding(2, "HALF_UP")),
		start_date=_to_date(start_date),
		first_due_date=_to_date(first_due_date),
		periods=int(periods),
		rate=InterestRate(annual_rate=Decimal(str(annual_rate))),
		day_count=DayCountConvention(str(day_count)),
		amortization=str(amortization),
		payment_frequency=str(payment_frequency),
		principal_grace_periods=int(principal_grace_periods),
		fee_rule=fee_rule,
	)
	lines = build_schedule(inp)
	return {
		"currency": currency,
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


@frappe.whitelist()
def preview_schedule_with_metrics(**kwargs) -> dict:
	"""
	Preview schedule and return cashflow metrics hook set.
	Current metrics: XIRR from borrower cashflows.
	"""
	out = preview_schedule(**kwargs)
	lines = out["lines"]
	flows = build_loan_cashflows(
		principal=Decimal(str(kwargs["principal"])),
		disbursement_date=_to_date(str(kwargs["start_date"])),
		due_lines=lines,
	)
	try:
		irr = xirr(flows)
	except Exception:
		irr = None
	out["metrics"] = {"xirr": irr}
	return out


def _to_decimal(value: str | int | float | Decimal) -> Decimal:
	return Decimal(str(value))


def _jsonable(obj):
	if isinstance(obj, Decimal):
		return str(obj)
	if isinstance(obj, date):
		return obj.isoformat()
	if isinstance(obj, dict):
		return {k: _jsonable(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_jsonable(v) for v in obj]
	return obj


def _assert_product_bookable(product_name: str):
	prod = frappe.get_doc("Finance Product", product_name)
	if prod.status != "ACTIVE":
		frappe.throw(frappe._("Finance Product must be ACTIVE to book contracts"))
	return prod


def _contract_to_quote_request(contract) -> QuoteRequest:
	return QuoteRequest(
		principal=_to_decimal(contract.current_outstanding or contract.principal),
		currency=str(contract.currency),
		annual_rate=_to_decimal(contract.annual_rate),
		start_date=contract.start_date,
		first_due_date=contract.first_due_date,
		periods=int(contract.periods),
		amortization=str(contract.amortization),
		payment_frequency=str(contract.payment_frequency),
		day_count=str(contract.day_count or "ACT_365F"),
	)


def _quote_request_from_saved(req: dict) -> QuoteRequest:
	def _parse_date(val):
		if val is None:
			return date.today()
		if isinstance(val, date):
			return val
		s = str(val)
		return date.fromisoformat(s[:10])

	fv = req.get("fee_value")
	return QuoteRequest(
		principal=Decimal(str(req["principal"])),
		currency=str(req["currency"]),
		annual_rate=Decimal(str(req["annual_rate"])),
		start_date=_parse_date(req["start_date"]),
		first_due_date=_parse_date(req["first_due_date"]),
		periods=int(req["periods"]),
		amortization=str(req["amortization"]),
		payment_frequency=str(req["payment_frequency"]),
		day_count=str(req.get("day_count") or "ACT_365F"),
		principal_grace_periods=int(req.get("principal_grace_periods") or 0),
		fee_type=req.get("fee_type"),
		fee_value=Decimal(str(fv)) if fv is not None else None,
		fee_applies_each_period=bool(req.get("fee_applies_each_period", True)),
	)


def _save_calc_run(
	run_type: str,
	input_payload: dict,
	output_payload: dict,
	explain_payload: dict,
	contract_account: str | None = None,
	idempotency_key: str | None = None,
	event_type: str | None = None,
	schedule_version: int | None = None,
) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Finance Calc Run",
			"contract_account": contract_account,
			"schedule_version": int(schedule_version or 0),
			"run_type": run_type,
			"run_status": "SUCCESS",
			"idempotency_key": idempotency_key,
			"input_hash": payload_hash(input_payload),
			"input_json": json.dumps(_jsonable(input_payload), sort_keys=True, separators=(",", ":")),
			"output_json": json.dumps(_jsonable(output_payload), sort_keys=True, separators=(",", ":")),
			"explain_json": json.dumps(_jsonable(explain_payload), sort_keys=True, separators=(",", ":")),
			"event_type": event_type or run_type,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _publish_finance_event(event_type: str, aggregate_type: str, aggregate_id: str, payload: dict) -> str:
	event_doc = frappe.get_doc(
		{
			"doctype": "Finance Event Outbox",
			"event_type": event_type,
			"aggregate_type": aggregate_type,
			"aggregate_id": aggregate_id,
			"status": "PENDING",
			"payload_hash": payload_hash(payload),
			"payload_json": json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")),
			"retry_count": 0,
		}
	)
	event_doc.insert(ignore_permissions=True)
	return event_doc.name


def _extract_fx_rate(contract) -> Decimal:
	mode = str(contract.fx_valuation_mode or "SPOT")
	if mode == "FORWARD" and contract.fx_forward_rate:
		return _to_decimal(contract.fx_forward_rate)
	return Decimal("1")


@frappe.whitelist()
def quote_finance_product(
	principal: str,
	currency: str,
	annual_rate: str,
	start_date: str,
	first_due_date: str,
	periods: int = 12,
	amortization: str = "ANNUITY",
	payment_frequency: str = "MONTHLY",
	day_count: str = "ACT_365F",
	principal_grace_periods: int = 0,
	fee_type: str | None = None,
	fee_value: str | None = None,
	fee_applies_each_period: int = 1,
	idempotency_key: str | None = None,
) -> dict:
	if idempotency_key:
		cached = get_cached_idempotent_result("quote_finance_product", idempotency_key)
		if cached:
			return cached
	req = QuoteRequest(
		principal=_to_decimal(principal),
		currency=str(currency),
		annual_rate=_to_decimal(annual_rate),
		start_date=_to_date(start_date),
		first_due_date=_to_date(first_due_date),
		periods=int(periods),
		amortization=str(amortization),
		payment_frequency=str(payment_frequency),
		day_count=str(day_count),
		principal_grace_periods=int(principal_grace_periods),
		fee_type=str(fee_type) if fee_type else None,
		fee_value=_to_decimal(fee_value) if fee_value is not None else None,
		fee_applies_each_period=bool(int(fee_applies_each_period)),
	)
	quote = build_quote(req)
	explain = make_explainability(req=req, quote_out=quote, event_type="QUOTE")
	run_name = _save_calc_run(
		run_type="QUOTE",
		input_payload={"request": req.__dict__},
		output_payload=quote,
		explain_payload=explain,
		idempotency_key=idempotency_key,
		event_type="QUOTE",
	)
	out = {"quote": quote, "explainability": explain, "calc_run": run_name}
	if idempotency_key:
		set_cached_idempotent_result("quote_finance_product", idempotency_key, out)
	return out


@frappe.whitelist()
def create_finance_contract(
	product: str,
	customer_name: str,
	principal: str,
	currency: str,
	annual_rate: str,
	start_date: str,
	first_due_date: str,
	periods: int = 12,
	amortization: str = "ANNUITY",
	payment_frequency: str = "MONTHLY",
	day_count: str = "ACT_365F",
	country_code: str = "INTL",
	company_code: str | None = None,
	branch_code: str | None = None,
	fx_valuation_mode: str = "SPOT",
	fx_rate_source: str = "MARKET",
	fx_forward_rate: str | None = None,
	fx_valuation_date: str | None = None,
	idempotency_key: str | None = None,
) -> dict:
	if idempotency_key:
		cached = get_cached_idempotent_result("create_finance_contract", idempotency_key)
		if cached:
			return cached
	prod_doc = _assert_product_bookable(product)
	req = QuoteRequest(
		principal=_to_decimal(principal),
		currency=str(currency),
		annual_rate=_to_decimal(annual_rate),
		start_date=_to_date(start_date),
		first_due_date=_to_date(first_due_date),
		periods=int(periods),
		amortization=str(amortization),
		payment_frequency=str(payment_frequency),
		day_count=str(day_count),
	)
	quote = build_quote(req)
	explain = make_explainability(req=req, quote_out=quote, event_type="CONTRACT_CREATE")
	contract = frappe.get_doc(
		{
			"doctype": "Finance Contract Account",
			"product": product,
			"customer_name": customer_name,
			"status": "ACTIVE",
			"company_code": company_code or getattr(prod_doc, "company_code", None) or "DEFAULT",
			"branch_code": branch_code or getattr(prod_doc, "branch_code", None) or "HQ",
			"country_code": country_code,
			"currency": currency,
			"principal": _to_decimal(principal),
			"current_outstanding": _to_decimal(principal),
			"annual_rate": _to_decimal(annual_rate),
			"periods": int(periods),
			"amortization": amortization,
			"payment_frequency": payment_frequency,
			"day_count": day_count,
			"fx_valuation_mode": fx_valuation_mode,
			"fx_rate_source": fx_rate_source,
			"fx_forward_rate": _to_decimal(fx_forward_rate) if fx_forward_rate is not None else None,
			"fx_valuation_date": _to_date(fx_valuation_date) if fx_valuation_date else None,
			"start_date": _to_date(start_date),
			"first_due_date": _to_date(first_due_date),
			"ifrs9_stage": "STAGE_1",
		}
	)
	contract.insert(ignore_permissions=True)
	run_name = _save_calc_run(
		run_type="CONTRACT_CREATE",
		input_payload={"request": req.__dict__, "product": product, "customer_name": customer_name},
		output_payload=quote,
		explain_payload=explain,
		contract_account=contract.name,
		idempotency_key=idempotency_key,
		event_type="CONTRACT_CREATE",
	)
	contract.last_calc_run = run_name
	contract.save(ignore_permissions=True)
	_publish_finance_event(
		event_type="CONTRACT_CREATED",
		aggregate_type="Finance Contract Account",
		aggregate_id=contract.name,
		payload={"contract_account": contract.name, "calc_run": run_name, "event_type": "CONTRACT_CREATED"},
	)
	out = {"contract_account": contract.name, "calc_run": run_name, "quote": quote, "explainability": explain}
	if idempotency_key:
		set_cached_idempotent_result("create_finance_contract", idempotency_key, out)
	return out


@frappe.whitelist()
def recalculate_finance_contract(
	contract_account: str,
	event_type: str = "RECALCULATION",
	override_annual_rate: str | None = None,
	idempotency_key: str | None = None,
) -> dict:
	cache_ns = f"recalculate_finance_contract:{contract_account}"
	if idempotency_key:
		cached = get_cached_idempotent_result(cache_ns, idempotency_key)
		if cached:
			return cached
	contract = frappe.get_doc("Finance Contract Account", contract_account)
	rate = _to_decimal(override_annual_rate) if override_annual_rate else _to_decimal(contract.annual_rate)
	base_currency = contract.currency
	fx_rate = _extract_fx_rate(contract)
	req = QuoteRequest(
		principal=_to_decimal(contract.current_outstanding or contract.principal),
		currency=base_currency,
		annual_rate=rate,
		start_date=contract.start_date,
		first_due_date=contract.first_due_date,
		periods=int(contract.periods),
		amortization=contract.amortization,
		payment_frequency=contract.payment_frequency,
		day_count=contract.day_count,
	)
	quote = build_quote(req)
	if fx_rate != Decimal("1"):
		for line in quote.get("lines", []):
			for key in ("opening_principal", "interest", "principal", "fees", "total_due", "closing_principal"):
				line[key] = str((_to_decimal(line[key]) * fx_rate).quantize(Decimal("0.01")))
		for key in ("principal", "interest", "fees", "total_due"):
			quote["totals"][key] = str((_to_decimal(quote["totals"][key]) * fx_rate).quantize(Decimal("0.01")))
		quote["fx_valuation"] = {
			"mode": contract.fx_valuation_mode,
			"source": contract.fx_rate_source,
			"rate_applied": str(fx_rate),
			"valuation_date": str(contract.fx_valuation_date) if contract.fx_valuation_date else None,
		}

	explain = make_explainability(req=req, quote_out=quote, event_type=event_type)
	run_name = _save_calc_run(
		run_type="RECALCULATION",
		input_payload={"request": req.__dict__, "event_type": event_type},
		output_payload=quote,
		explain_payload=explain,
		contract_account=contract.name,
		idempotency_key=idempotency_key,
		event_type=event_type,
	)
	contract.last_calc_run = run_name
	if event_type == "DEFAULT":
		contract.ifrs9_stage = "STAGE_3"
		contract.status = "DEFAULTED"
	elif event_type == "RESTRUCTURE":
		contract.ifrs9_stage = "STAGE_2"
		contract.status = "RESTRUCTURED"
	elif event_type == "EARLY_SETTLEMENT":
		contract.status = "SETTLED"
		contract.current_outstanding = 0
	contract.save(ignore_permissions=True)
	_publish_finance_event(
		event_type=event_type,
		aggregate_type="Finance Contract Account",
		aggregate_id=contract.name,
		payload={"contract_account": contract.name, "calc_run": run_name, "event_type": event_type},
	)
	out = {"contract_account": contract.name, "calc_run": run_name, "quote": quote, "explainability": explain}
	if idempotency_key:
		set_cached_idempotent_result(cache_ns, idempotency_key, out)
	return out


@frappe.whitelist()
def get_calc_run_explainability(calc_run: str | None = None, contract_account: str | None = None, limit: int = 20) -> list[dict]:
	filters: dict = {}
	if calc_run:
		filters["name"] = calc_run
	if contract_account:
		filters["contract_account"] = contract_account
	rows = frappe.get_all(
		"Finance Calc Run",
		filters=filters,
		fields=["name", "contract_account", "run_type", "event_type", "input_hash", "output_json", "explain_json", "creation"],
		order_by="creation desc",
		limit_page_length=int(limit),
	)
	out: list[dict] = []
	for row in rows:
		try:
			explain = json.loads(row.explain_json or "{}")
		except Exception:
			explain = {}
		try:
			output_payload = json.loads(row.output_json or "{}")
		except Exception:
			output_payload = {}
		out.append(
			{
				"calc_run": row.name,
				"contract_account": row.contract_account,
				"run_type": row.run_type,
				"event_type": row.event_type,
				"input_hash": row.input_hash,
				"output": output_payload,
				"explainability": explain,
				"created_at": row.creation,
			}
		)
	return out


@frappe.whitelist()
def record_schedule_snapshot_for_contract(contract_account: str, idempotency_key: str | None = None) -> dict:
	"""Immutable schedule version tied to contract; stores inputs/outputs on Finance Calc Run."""
	cache_ns = f"schedule_snapshot:{contract_account}"
	if idempotency_key:
		cached = get_cached_idempotent_result(cache_ns, idempotency_key)
		if cached:
			return cached
	contract = frappe.get_doc("Finance Contract Account", contract_account)
	req = _contract_to_quote_request(contract)
	quote = build_quote(req)
	explain = make_explainability(req=req, quote_out=quote, event_type="SCHEDULE_SNAPSHOT")
	next_ver = int(contract.schedule_version_seq or 0) + 1
	input_payload = {"request": asdict(req), "contract_account": contract_account, "schedule_version": next_ver}
	run_name = _save_calc_run(
		run_type="SCHEDULE_SNAPSHOT",
		input_payload=input_payload,
		output_payload=quote,
		explain_payload=explain,
		contract_account=contract.name,
		idempotency_key=idempotency_key,
		event_type="SCHEDULE_SNAPSHOT",
		schedule_version=next_ver,
	)
	contract.schedule_version_seq = next_ver
	contract.last_calc_run = run_name
	contract.save(ignore_permissions=True)
	out = {"contract_account": contract.name, "calc_run": run_name, "schedule_version": next_ver, "quote": quote}
	if idempotency_key:
		set_cached_idempotent_result(cache_ns, idempotency_key, out)
	return out


@frappe.whitelist()
def list_schedule_versions(contract_account: str, limit: int = 50) -> list[dict]:
	return frappe.get_all(
		"Finance Calc Run",
		filters={"contract_account": contract_account, "run_type": "SCHEDULE_SNAPSHOT"},
		fields=["name", "schedule_version", "input_hash", "creation"],
		order_by="schedule_version desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def replay_finance_calc_run(calc_run: str) -> dict:
	"""Recompute from stored inputs and compare to persisted outputs (determinism check)."""
	doc = frappe.get_doc("Finance Calc Run", calc_run)
	payload = json.loads(doc.input_json or "{}")
	if "request" not in payload:
		frappe.throw(frappe._("Replay only supported when input_json contains a schedule request"))
	req = _quote_request_from_saved(payload["request"])
	new_quote = build_quote(req)
	stored = json.loads(doc.output_json or "{}")
	a = json.dumps(_jsonable(new_quote), sort_keys=True, separators=(",", ":"))
	b = json.dumps(_jsonable(stored), sort_keys=True, separators=(",", ":"))
	return {"calc_run": calc_run, "outputs_identical": a == b, "recomputed": new_quote, "stored": stored}


@frappe.whitelist()
def submit_finance_product_status_change(product: str, proposed_status: str) -> dict:
	from frappe.utils import now_datetime

	allowed = {"DRAFT", "ACTIVE", "SUSPENDED", "RETIRED"}
	if proposed_status not in allowed:
		frappe.throw(frappe._("Invalid lifecycle status"))
	doc = frappe.get_doc("Finance Product", product)
	doc.pending_status = proposed_status
	doc.status_submitted_by = frappe.session.user
	doc.status_submitted_on = now_datetime()
	doc.status_approved_by = None
	doc.status_approved_on = None
	doc.save(ignore_permissions=True)
	return {"product": product, "pending_status": proposed_status}


@frappe.whitelist()
def approve_finance_product_status_change(product: str) -> dict:
	from frappe.utils import now_datetime

	doc = frappe.get_doc("Finance Product", product)
	if not doc.pending_status:
		frappe.throw(frappe._("No pending status change"))
	if doc.status_submitted_by == frappe.session.user:
		frappe.throw(frappe._("Checker must differ from maker"))
	doc.status = doc.pending_status
	doc.pending_status = None
	doc.status_approved_by = frappe.session.user
	doc.status_approved_on = now_datetime()
	doc.save(ignore_permissions=True)
	return {"product": product, "status": doc.status}


@frappe.whitelist()
def reject_finance_product_status_change(product: str, reason: str = "") -> dict:
	doc = frappe.get_doc("Finance Product", product)
	doc.pending_status = None
	doc.save(ignore_permissions=True)
	return {"product": product, "rejected": True, "reason": reason}


@frappe.whitelist()
def list_finance_accounting_templates(event_type: str | None = None, status: str = "ACTIVE") -> list[dict]:
	filters: dict = {"status": status}
	if event_type:
		filters["event_type"] = event_type
	return frappe.get_all(
		"Finance Accounting Event Template",
		filters=filters,
		fields=["name", "template_code", "title", "event_type", "product", "status"],
		order_by="modified desc",
		limit_page_length=200,
	)


@frappe.whitelist()
def simulate_finance_contract_scenario(
	contract_account: str,
	scenario_name: str,
	rate_shift_bps: int = 0,
	fee_multiplier: str = "1",
	fx_rate_override: str | None = None,
	idempotency_key: str | None = None,
) -> dict:
	cache_ns = f"simulate_finance_contract_scenario:{contract_account}:{scenario_name}"
	if idempotency_key:
		cached = get_cached_idempotent_result(cache_ns, idempotency_key)
		if cached:
			return cached
	contract = frappe.get_doc("Finance Contract Account", contract_account)
	shift = Decimal(str(rate_shift_bps)) / Decimal("10000")
	req = QuoteRequest(
		principal=_to_decimal(contract.current_outstanding or contract.principal),
		currency=contract.currency,
		annual_rate=_to_decimal(contract.annual_rate) + shift,
		start_date=contract.start_date,
		first_due_date=contract.first_due_date,
		periods=int(contract.periods),
		amortization=contract.amortization,
		payment_frequency=contract.payment_frequency,
		day_count=contract.day_count,
		fee_type="PERCENT",
		fee_value=Decimal("0.01") * Decimal(str(fee_multiplier)),
	)
	quote = build_quote(req)
	if fx_rate_override is not None:
		override = _to_decimal(fx_rate_override)
		for line in quote.get("lines", []):
			for key in ("opening_principal", "interest", "principal", "fees", "total_due", "closing_principal"):
				line[key] = str((_to_decimal(line[key]) * override).quantize(Decimal("0.01")))
		for key in ("principal", "interest", "fees", "total_due"):
			quote["totals"][key] = str((_to_decimal(quote["totals"][key]) * override).quantize(Decimal("0.01")))
		quote["fx_override_rate"] = str(override)
	explain = make_explainability(req=req, quote_out=quote, event_type="SIMULATION")
	input_payload = {
		"contract_account": contract_account,
		"scenario_name": scenario_name,
		"rate_shift_bps": int(rate_shift_bps),
		"fee_multiplier": str(fee_multiplier),
		"fx_rate_override": str(fx_rate_override) if fx_rate_override is not None else None,
	}
	scenario_doc = frappe.get_doc(
		{
			"doctype": "Finance Scenario Run",
			"contract_account": contract_account,
			"scenario_name": scenario_name,
			"run_status": "SUCCESS",
			"idempotency_key": idempotency_key,
			"input_hash": payload_hash(input_payload),
			"input_json": json.dumps(_jsonable(input_payload), sort_keys=True, separators=(",", ":")),
			"scenario_json": json.dumps({"rate_shift_bps": rate_shift_bps, "fee_multiplier": str(fee_multiplier)}, sort_keys=True),
			"output_json": json.dumps(_jsonable(quote), sort_keys=True, separators=(",", ":")),
			"explain_json": json.dumps(_jsonable(explain), sort_keys=True, separators=(",", ":")),
		}
	)
	scenario_doc.insert(ignore_permissions=True)
	_publish_finance_event(
		event_type="SCENARIO_SIMULATED",
		aggregate_type="Finance Contract Account",
		aggregate_id=contract_account,
		payload={"contract_account": contract_account, "scenario_run": scenario_doc.name, "scenario_name": scenario_name},
	)
	out = {"scenario_run": scenario_doc.name, "contract_account": contract_account, "quote": quote, "explainability": explain}
	if idempotency_key:
		set_cached_idempotent_result(cache_ns, idempotency_key, out)
	return out


@frappe.whitelist()
def list_finance_outbox_events(status: str | None = None, limit: int = 100) -> list[dict]:
	filters = {}
	if status:
		filters["status"] = status
	return frappe.get_all(
		"Finance Event Outbox",
		filters=filters,
		fields=["name", "event_type", "aggregate_type", "aggregate_id", "status", "payload_hash", "retry_count", "creation"],
		order_by="creation desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def convert_amount(
	amount: str,
	source_currency: str,
	target_currency: str,
	rate: str,
	target_precision: int = 2,
	rounding_mode: str = "HALF_UP",
) -> dict:
	"""Multi-currency conversion endpoint with deterministic rounding."""
	src_rounding = CurrencyRounding(precision=int(target_precision), mode=str(rounding_mode))
	target_rounding_obj = CurrencyRounding(precision=int(target_precision), mode=str(rounding_mode))
	money = Money(amount=Decimal(str(amount)), currency=str(source_currency), rounding=src_rounding)
	quote = FXQuote(
		source_currency=str(source_currency),
		target_currency=str(target_currency),
		rate=Decimal(str(rate)),
	)
	out = convert_money(
		amount=money,
		target_currency=str(target_currency),
		quote=quote,
		target_rounding=target_rounding_obj,
	)
	return {
		"source_currency": source_currency,
		"target_currency": target_currency,
		"amount": str(money.amount),
		"rate": str(quote.rate),
		"converted_amount": str(out.amount),
	}


@frappe.whitelist()
def get_standards_profile() -> dict:
	"""Expose standards profile for governance dashboards and audits."""
	return _get_standards_profile()


@frappe.whitelist()
def submit_policy_version(policy_name: str, version: str, payload: str, effective_from: str | None = None) -> dict:
	import json
	from .governance import submit_policy_version as _submit
	obj = json.loads(payload) if isinstance(payload, str) else payload
	if not isinstance(obj, dict):
		frappe.throw(frappe._("payload must be a JSON object"))
	return _submit("omnexa_finance_engine", policy_name=policy_name, version=version, payload=obj, effective_from=effective_from)


@frappe.whitelist()
def approve_policy_version(policy_name: str, version: str) -> dict:
	from .governance import approve_policy_version as _approve
	return _approve("omnexa_finance_engine", policy_name=policy_name, version=version)


@frappe.whitelist()
def create_audit_snapshot(process_name: str, inputs: str, outputs: str, policy_ref: str | None = None) -> dict:
	import json
	from .governance import create_audit_snapshot as _snap
	in_obj = json.loads(inputs) if isinstance(inputs, str) else inputs
	out_obj = json.loads(outputs) if isinstance(outputs, str) else outputs
	if not isinstance(in_obj, dict) or not isinstance(out_obj, dict):
		frappe.throw(frappe._("inputs/outputs must be JSON objects"))
	return _snap("omnexa_finance_engine", process_name=process_name, inputs=in_obj, outputs=out_obj, policy_ref=policy_ref)


@frappe.whitelist()
def get_governance_overview() -> dict:
	from .governance import governance_overview as _overview
	return _overview("omnexa_finance_engine")


@frappe.whitelist()
def reject_policy_version(policy_name: str, version: str, reason: str = "") -> dict:
	from .governance import reject_policy_version as _reject
	return _reject("omnexa_finance_engine", policy_name=policy_name, version=version, reason=reason)


@frappe.whitelist()
def list_policy_versions(policy_name: str | None = None) -> list[dict]:
	from .governance import list_policy_versions as _list
	return _list("omnexa_finance_engine", policy_name=policy_name)


@frappe.whitelist()
def list_audit_snapshots(process_name: str | None = None, limit: int = 100) -> list[dict]:
	from .governance import list_audit_snapshots as _list
	return _list("omnexa_finance_engine", process_name=process_name, limit=int(limit))


@frappe.whitelist()
def get_regulatory_dashboard() -> dict:
	"""Unified compliance dashboard payload for this app."""
	from .governance import governance_overview
	from .standards_profile import get_standards_profile
	std = get_standards_profile()
	gov = governance_overview("omnexa_finance_engine")
	return {
		"app": "omnexa_finance_engine",
		"standards": std.get("standards", []),
		"activity_controls": std.get("activity_controls", []),
		"governance": gov,
		"compliance_score": _compute_compliance_score(std=std, gov=gov),
	}


def _compute_compliance_score(std: dict, gov: dict) -> int:
	"""Simple normalized readiness score (0..100) for executive monitoring."""
	base = min(50, 5 * len(std.get("standards", [])))
	controls = min(30, 3 * len(std.get("activity_controls", [])))
	approved = int(gov.get("policies_approved", 0) or 0)
	pending = int(gov.get("policies_pending", 0) or 0)
	governance = min(20, approved * 2)
	if pending > 0:
		governance = max(0, governance - min(10, pending))
	return int(base + controls + governance)
