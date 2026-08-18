# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from printechs_support.printechs_support_system.prai_promotion_assistant import (
	evaluate_promotion_pos_availability,
	fetch_all_pos_promotions,
	promotion_doctype_available,
)


def run_health_checks(*, source_project: str | None = None) -> list[dict]:
	"""Evaluate active health rule templates against live ERPNext data."""
	templates = frappe.get_all(
		"PRAI Studio Health Rule Template",
		filters={"is_active": 1},
		fields=["name", "rule_code", "title", "rule_key", "default_severity", "remediation_hint"],
		order_by="rule_code asc",
	)
	results: list[dict] = []
	for template in templates:
		runners = {
			"promotion_not_on_pos": _check_promotion_not_on_pos,
			"promotion_inactive_status": _check_promotion_inactive_status,
			"promotion_usage_limit_reached": _check_promotion_usage_limit_reached,
		}
		runner = runners.get(template.rule_key)
		if not runner:
			continue
		result = runner(template, source_project=source_project)
		results.append(result)
	return results


def _check_promotion_not_on_pos(template: dict, *, source_project: str | None = None) -> dict:
	if not promotion_doctype_available():
		return _result(template, "Pass", "POS Promotion DocType is not installed.", "")

	issues: list[str] = []
	for row in fetch_all_pos_promotions(limit=200) or []:
		if not cint(row.get("is_active")):
			continue
		ok, reasons = evaluate_promotion_pos_availability(row)
		if ok:
			continue
		label = row.get("promotion_code") or row.get("name")
		issues.append(f"{label}: {', '.join(reasons[:3])}")

	if not issues:
		return _result(template, "Pass", "All active promotions are available on POS.", "")
	detail = "\n".join(f"- {line}" for line in issues[:30])
	summary = _("{0} active promotion(s) are not available on POS.").format(len(issues))
	status = template.get("default_severity") or "Warning"
	if status == "Pass":
		status = "Warning"
	return _result(template, status, summary, detail)


def _check_promotion_inactive_status(template: dict, *, source_project: str | None = None) -> dict:
	if not promotion_doctype_available():
		return _result(template, "Pass", "POS Promotion DocType is not installed.", "")

	issues: list[str] = []
	for row in fetch_all_pos_promotions(limit=200) or []:
		if not cint(row.get("is_active")):
			continue
		status = (row.get("status") or "").strip()
		if status in {"Active", "Approved"}:
			continue
		label = row.get("promotion_code") or row.get("name")
		issues.append(f"{label}: Is Active=Yes but Status={status or 'blank'}")

	if not issues:
		return _result(template, "Pass", "No active promotions with invalid status.", "")
	detail = "\n".join(f"- {line}" for line in issues[:30])
	return _result(
		template,
		template.get("default_severity") or "Warning",
		_("{0} promotion(s) have Is Active but status is not Active/Approved.").format(len(issues)),
		detail,
	)


def _check_promotion_usage_limit_reached(template: dict, *, source_project: str | None = None) -> dict:
	if not promotion_doctype_available():
		return _result(template, "Pass", "POS Promotion DocType is not installed.", "")

	issues: list[str] = []
	for row in fetch_all_pos_promotions(limit=200) or []:
		max_usage = cint(row.get("max_usage"))
		usage_count = cint(row.get("usage_count"))
		if max_usage and usage_count >= max_usage:
			label = row.get("promotion_code") or row.get("name")
			issues.append(f"{label}: usage {usage_count}/{max_usage}")

	if not issues:
		return _result(template, "Pass", "No promotions have reached usage limits.", "")
	detail = "\n".join(f"- {line}" for line in issues[:30])
	return _result(
		template,
		template.get("default_severity") or "Warning",
		_("{0} promotion(s) reached usage limit.").format(len(issues)),
		detail,
	)


def _result(template: dict, status: str, summary: str, detail: str) -> dict:
	return {
		"rule_template": template.get("name"),
		"rule_key": template.get("rule_key"),
		"result_status": status,
		"summary": summary,
		"detail": detail,
		"include_in_generation": 1 if status in {"Warning", "Fail"} else 0,
	}


def ensure_default_health_rule_templates() -> None:
	defaults = [
		{
			"rule_code": "PROMO-NOT-ON-POS",
			"title": "Active promotion not available on POS",
			"rule_key": "promotion_not_on_pos",
			"description": "Finds promotions marked active in ERPNext that will not sync to Modern POS.",
			"remediation_hint": "Check status, dates, scope, and usage limits; then sync Modern POS.",
			"default_severity": "Warning",
		},
		{
			"rule_code": "PROMO-STATUS-MISMATCH",
			"title": "Promotion active flag with invalid status",
			"rule_key": "promotion_inactive_status",
			"description": "Finds promotions with Is Active but Status not Active/Approved.",
			"remediation_hint": "Set Status to Active or Approved, or disable Is Active.",
			"default_severity": "Warning",
		},
		{
			"rule_code": "PROMO-USAGE-LIMIT",
			"title": "Promotion usage limit reached",
			"rule_key": "promotion_usage_limit_reached",
			"description": "Finds promotions that reached max usage and may stop applying.",
			"remediation_hint": "Increase max usage or create a replacement promotion.",
			"default_severity": "Warning",
		},
	]
	for row in defaults:
		if frappe.db.exists("PRAI Studio Health Rule Template", row["rule_code"]):
			continue
		frappe.get_doc({"doctype": "PRAI Studio Health Rule Template", **row, "is_active": 1}).insert(
			ignore_permissions=True
		)
