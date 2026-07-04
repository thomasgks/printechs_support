# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Live Modern POS promotion catalog and configuration guide for PRAI."""

from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, format_datetime, get_datetime, now_datetime, strip_html

POS_SYNC_STATUSES = frozenset({"Active", "Approved"})

BENEFIT_LABELS: dict[str, str] = {
	"DISCOUNT_PERCENT_LINE": "Percent discount on line item",
	"DISCOUNT_AMOUNT_LINE": "Fixed amount off line item",
	"DISCOUNT_PERCENT_CART": "Percent discount on cart total",
	"DISCOUNT_AMOUNT_CART": "Fixed amount off cart total",
	"SPECIAL_PRICE": "Special price",
	"FREE_ITEM": "Free item (BOGO / gift)",
	"BUY_X_GET_Y": "Buy X get Y",
	"BUNDLE_PRICE": "Bundle price",
	"MIX_MATCH_PRICE": "Mix-and-match price",
	"POINTS_MULTIPLIER": "Loyalty points multiplier",
	"GIFT_WITH_PURCHASE": "Gift with purchase",
}

SCOPE_LABELS: dict[str, str] = {
	"GLOBAL": "All stores",
	"STORE_SPECIFIC": "Selected stores only",
	"WAREHOUSE_SPECIFIC": "Selected warehouses",
	"POS_PROFILE_SPECIFIC": "Selected POS Profiles",
	"EXCLUDED_STORES": "All stores except excluded list",
}


def promotion_doctype_available() -> bool:
	return bool(frappe.db.table_exists("POS Promotion"))


def can_read_promotions() -> bool:
	return promotion_doctype_available() and bool(frappe.has_permission("POS Promotion", "read"))


_CONFIGURE_INTENT_TERMS = frozenset(
	{"configure", "configuration", "setup", "set", "edit", "activate", "enable", "how", "change", "update"}
)


def _tokenize(text: str) -> list[str]:
	return [part for part in re.split(r"[^\w]+", (text or "").lower()) if len(part) >= 2]


def _has_configure_intent(message: str) -> bool:
	return bool(_CONFIGURE_INTENT_TERMS & set(_tokenize(message)))


def find_promotion_from_message(message: str):
	"""Resolve a POS Promotion doc from a user message (code in brackets, code token, or name)."""
	if not can_read_promotions():
		return None

	text = (message or "").strip()
	if not text:
		return None

	paren = re.search(r"\(([A-Z0-9_]+)\)", text)
	if paren:
		code = paren.group(1)
		name = frappe.db.get_value("POS Promotion", {"promotion_code": code}, "name")
		if not name:
			name = frappe.db.exists("POS Promotion", code)
		if name:
			return frappe.get_doc("POS Promotion", name)

	compact = re.sub(r"[\W_]+", "", text.upper())
	for row in fetch_all_pos_promotions(limit=100) or []:
		code = (row.get("promotion_code") or "").strip().upper()
		if code and code in compact:
			return frappe.get_doc("POS Promotion", row.name)

	lower = text.lower()
	best_name = ""
	best_doc = None
	for row in fetch_all_pos_promotions(limit=100) or []:
		promo_name = (row.get("promotion_name") or "").strip()
		if len(promo_name) >= 6 and promo_name.lower() in lower:
			if len(promo_name) > len(best_name):
				best_name = promo_name
				best_doc = row.name
	if best_doc:
		return frappe.get_doc("POS Promotion", best_doc)
	return None


def _doc_as_availability_row(doc) -> dict:
	return {
		"name": doc.name,
		"promotion_code": doc.promotion_code,
		"promotion_name": doc.promotion_name,
		"status": doc.status,
		"is_active": doc.is_active,
		"start_datetime": doc.start_datetime,
		"end_datetime": doc.end_datetime,
		"promotion_scope": doc.promotion_scope,
		"store_codes": doc.get("store_codes"),
		"warehouse_codes": doc.get("warehouse_codes"),
		"pos_profile_codes": doc.get("pos_profile_codes"),
		"max_total_usage": doc.get("max_total_usage"),
		"current_usage_count": doc.get("current_usage_count"),
	}


def _format_condition_line(row) -> str:
	condition_type = (row.condition_type or "").replace("_", " ").title()
	operator = row.operator or ""
	value_text = (row.value_text or "").strip()
	value_number = row.value_number
	parts = [condition_type]
	if operator:
		parts.append(operator)
	if value_number not in (None, ""):
		parts.append(str(value_number))
	if value_text:
		parts.append(value_text)
	return " ".join(parts)


def _format_benefit_line(row) -> str:
	benefit_type = row.benefit_type or ""
	label = BENEFIT_LABELS.get(benefit_type, benefit_type.replace("_", " ").title())
	chunks = [label]
	if row.bundle_price:
		chunks.append(_("bundle price {0}").format(row.bundle_price))
	if row.value_number not in (None, "", 0.0) and "PERCENT" in benefit_type:
		chunks.append(f"{row.value_number}%")
	elif row.value_number not in (None, "", 0.0):
		chunks.append(str(row.value_number))
	if row.bundle_code:
		chunks.append(_("bundle {0}").format(row.bundle_code))
	if row.free_item_code:
		chunks.append(_("free item {0}").format(row.free_item_code))
	if row.value_text:
		try:
			payload = json.loads(row.value_text)
			if isinstance(payload, dict):
				if payload.get("RequiredQty"):
					chunks.append(_("qty {0}").format(payload.get("RequiredQty")))
				if payload.get("RequiredCategories"):
					chunks.append(_("categories {0}").format(", ".join(payload.get("RequiredCategories") or [])))
		except Exception:
			pass
	return " — ".join(chunks)


def format_single_promotion_guide(doc) -> str:
	row = _doc_as_availability_row(doc)
	available, reasons = evaluate_promotion_pos_availability(row)
	code = (doc.promotion_code or doc.name or "").strip()
	name = (doc.promotion_name or code).strip()
	lines = [_("Configure promotion: {0} ({1})").format(name, code), ""]

	lines.extend([_("Current status"), ""])
	status = doc.status or _("Unknown")
	active = _("Yes") if cint(doc.is_active) else _("No")
	lines.append(f"• {_('Status')}: {status} | {_('Is Active')}: {active}")
	if available:
		lines.append(f"• {_('Available on Modern POS now')}")
	else:
		lines.append(f"• {_('Not on POS yet')}: {'; '.join(reasons)}")
	lines.append("")

	lines.extend([_("Promotion settings"), ""])
	start = format_datetime(doc.start_datetime) if doc.start_datetime else "—"
	end = format_datetime(doc.end_datetime) if doc.end_datetime else "—"
	lines.append(f"1. {_('Scope')} — {_scope_label(doc.promotion_scope)}")
	lines.append(f"2. {_('Valid period')} — {start} {_('to')} {end}")
	if doc.description:
		lines.append(f"3. {_('Description')} — {strip_html(doc.description)}")
	step = 4
	for cond in doc.conditions or []:
		lines.append(f"{step}. {_('Condition')} — {_format_condition_line(cond)}")
		step += 1
	for benefit in doc.benefits or []:
		lines.append(f"{step}. {_('Benefit')} — {_format_benefit_line(benefit)}")
		step += 1
	if doc.time_slots:
		lines.append(f"{step}. {_('Time slots')} — {len(doc.time_slots)} {_('configured')}")
		step += 1
	if doc.tiers:
		lines.append(f"{step}. {_('Tiers')} — {len(doc.tiers)} {_('configured')}")
		step += 1

	lines.extend(["", _("Steps to enable on Modern POS"), ""])
	lines.append(f"1. {_('Open')} POS Promotion → {code} {_('in ERPNext')}.")
	lines.append(f"2. {_('Set Is Active = Yes and Status = Active or Approved')}.")
	lines.append(f"3. {_('Review conditions and benefits above, then Save')}.")
	lines.append(f"4. {_('Run Sync on the Modern POS terminal')}.")
	lines.append(f"5. {_('Test at checkout with qualifying items')}.")
	if doc.benefits and (doc.benefits[0].benefit_type or "") == "BUNDLE_PRICE":
		lines.append(
			f"6. {_('For bundle promotions, add the required quantity of eligible items before the bundle price applies')}."
		)
	return "\n".join(lines)


def try_build_specific_promotion_reply(message: str):
	"""Configure/help for one promotion identified in the user message."""
	if not _has_configure_intent(message):
		return None
	doc = find_promotion_from_message(message)
	if not doc:
		return None
	content = format_single_promotion_guide(doc)
	sources = [
		{
			"type": "erpnext",
			"name": doc.name,
			"title": doc.promotion_name or doc.promotion_code,
			"summary": _("Promotion configuration from ERPNext"),
			"url": f"/app/pos-promotion/{doc.name}",
		}
	]
	return content, "Live Data", doc.name, sources, False


def evaluate_promotion_pos_availability(row: dict) -> tuple[bool, list[str]]:
	"""Mirror Modern POS sync rules from modern_pos.api.promotion._get_active_promotion_filters."""
	reasons: list[str] = []
	now = now_datetime()

	if not cint(row.get("is_active")):
		reasons.append(_("Is Active is off"))

	status = (row.get("status") or "").strip()
	if status not in POS_SYNC_STATUSES:
		reasons.append(_("Status is {0} (must be Active or Approved)").format(status or _("blank")))

	start = row.get("start_datetime")
	end = row.get("end_datetime")
	if not start or not end:
		reasons.append(_("Start and end date/time are required"))
	else:
		start_dt = get_datetime(start)
		end_dt = get_datetime(end)
		if start_dt > now:
			reasons.append(_("Starts on {0} (not started yet)").format(format_datetime(start)))
		if end_dt < now:
			reasons.append(_("Ended on {0}").format(format_datetime(end)))

	max_total = cint(row.get("max_total_usage"))
	current_usage = cint(row.get("current_usage_count"))
	if max_total and current_usage >= max_total:
		reasons.append(_("Total usage limit reached ({0}/{1})").format(current_usage, max_total))

	scope = (row.get("promotion_scope") or "GLOBAL").upper()
	if scope == "STORE_SPECIFIC" and not (row.get("store_codes") or "").strip():
		reasons.append(_("Store-specific promotion has no store assigned"))
	if scope == "WAREHOUSE_SPECIFIC" and not (row.get("warehouse_codes") or "").strip():
		reasons.append(_("Warehouse-specific promotion has no warehouse assigned"))
	if scope == "POS_PROFILE_SPECIFIC" and not (row.get("pos_profile_codes") or "").strip():
		reasons.append(_("POS Profile promotion has no profile assigned"))

	return (not reasons, reasons)


def fetch_all_pos_promotions(*, limit: int = 100) -> list[dict] | None:
	if not can_read_promotions():
		return None
	return frappe.get_all(
		"POS Promotion",
		fields=[
			"name",
			"promotion_code",
			"promotion_name",
			"status",
			"is_active",
			"start_datetime",
			"end_datetime",
			"promotion_scope",
			"store_codes",
			"warehouse_codes",
			"pos_profile_codes",
			"max_total_usage",
			"current_usage_count",
			"priority",
			"description",
		],
		order_by="priority desc, promotion_name asc",
		limit_page_length=limit,
	)


def _benefit_summaries(parent_names: list[str]) -> dict[str, str]:
	if not parent_names:
		return {}
	rows = frappe.get_all(
		"POS Promotion Benefit",
		filters={"parent": ["in", parent_names]},
		fields=["parent", "benefit_type", "value_number", "value_text"],
		order_by="idx asc",
	)
	out: dict[str, str] = {}
	for row in rows:
		parent = row.parent
		if parent in out:
			continue
		label = BENEFIT_LABELS.get(row.benefit_type or "", row.benefit_type or _("Benefit"))
		value = row.value_number
		if value not in (None, "") and "PERCENT" in (row.benefit_type or ""):
			out[parent] = f"{label} ({value}%)"
		elif value not in (None, ""):
			out[parent] = f"{label} ({value})"
		else:
			out[parent] = label
	return out


def _promotion_label(row: dict) -> str:
	code = (row.get("promotion_code") or row.get("name") or "").strip()
	name = (row.get("promotion_name") or code or _("Untitled promotion")).strip()
	if code and code != name:
		return f"{name} ({code})"
	return name


def _scope_label(scope: str | None) -> str:
	key = (scope or "GLOBAL").upper()
	return SCOPE_LABELS.get(key, key.replace("_", " ").title())


def build_promotion_configuration_guide() -> str:
	return _(
		"Modern POS promotion configuration guide\n\n"
		"1. Open POS Promotion — In ERPNext, go to Modern POS → POS Promotion.\n"
		"2. Header — Set promotion code, name, priority, start/end date & time, and promotion scope "
		"(Global, Store, Warehouse, or POS Profile).\n"
		"3. Conditions — Define eligible items, brands, categories, minimum quantity/amount, customer segment, "
		"or payment method (INCLUDE_ITEM, MIN_QTY_ITEM, MIN_AMOUNT_CART, etc.).\n"
		"4. Benefits — Choose benefit type: line/cart percent or amount discount, special price, free item, "
		"bundle price, buy-X-get-Y, points multiplier, or gift with purchase.\n"
		"5. Time rules — Optional weekday mask and time slots for happy-hour style promotions.\n"
		"6. Stacking — Set stacking policy (Exclusive, Stackable, Best Only) and discount caps if needed.\n"
		"7. Activate — Enable Is Active, set Status to Active or Approved, and save.\n"
		"8. Sync — Run Sync on Modern POS so the terminal downloads eligible promotions.\n"
		"9. Test — Add qualifying items at checkout and confirm discount applies.\n\n"
		"When is a promotion available on POS?\n"
		"• Is Active = Yes\n"
		"• Status = Active or Approved\n"
		"• Current date/time is between start and end\n"
		"• Usage limits not exceeded\n"
		"• Store / warehouse / POS Profile scope matches the terminal\n"
		"• Terminal completed Sync after the promotion was saved"
	)


def format_promotion_catalog_reply(rows: list[dict], *, include_guide: bool = True) -> str:
	if not rows:
		body = _(
			"POS Promotion catalog\n\n"
			"No POS Promotion records were found in ERPNext.\n\n"
			"1. Create — Open POS Promotion and add your first promotion.\n"
			"2. Sync — Run Sync on Modern POS after saving.\n"
		)
		if include_guide:
			body += "\n\n" + build_promotion_configuration_guide()
		return body

	benefits = _benefit_summaries([row.name for row in rows])
	available: list[tuple[dict, str]] = []
	unavailable: list[tuple[dict, list[str]]] = []

	for row in rows:
		ok, reasons = evaluate_promotion_pos_availability(row)
		if ok:
			benefit = benefits.get(row.name, "")
			available.append((row, benefit))
		else:
			unavailable.append((row, reasons))

	lines = [
		_("POS Promotion catalog ({0} total)").format(len(rows)),
		"",
		_("Available on Modern POS now ({0})").format(len(available)),
		_("These match Modern POS sync rules (Active/Approved, valid dates, limits OK)."),
		"",
	]

	if available:
		for index, (row, benefit) in enumerate(available, start=1):
			end = row.get("end_datetime")
			end_text = format_datetime(end) if end else "—"
			extra = f" | {benefit}" if benefit else ""
			lines.append(
				f"{index}. {_promotion_label(row)} — {_scope_label(row.get('promotion_scope'))} | "
				f"{_('until')} {end_text}{extra}"
			)
	else:
		lines.append(f"• {_('None — check the not-available list below and fix settings, then Sync.')}")

	lines.extend(["", _("Not available on POS yet ({0})").format(len(unavailable)), ""])

	if unavailable:
		for index, (row, reasons) in enumerate(unavailable, start=1):
			status = row.get("status") or _("Unknown")
			active = _("Yes") if cint(row.get("is_active")) else _("No")
			reason_text = "; ".join(reasons[:3])
			lines.append(
				f"{index}. {_promotion_label(row)} — {_('Status')}: {status} | {_('Is Active')}: {active} | {reason_text}"
			)
	else:
		lines.append(f"• {_('All configured promotions are eligible for POS sync.')}")

	lines.extend(
		[
			"",
			_("After changing a promotion, run Sync on Modern POS. Store-specific promotions only appear on matching terminals."),
		]
	)

	if include_guide:
		lines.extend(["", build_promotion_configuration_guide()])

	return "\n".join(lines)


def build_promotion_assistant_reply(
	message: str,
	*,
	include_catalog: bool = True,
	include_guide: bool = False,
) -> tuple[str, str, str, list[dict], bool] | None:
	"""Return (content, source_type, reference, sources, suggest_escalation) or None."""
	if not can_read_promotions():
		return None

	rows = fetch_all_pos_promotions() or []
	if include_catalog:
		content = format_promotion_catalog_reply(rows, include_guide=include_guide)
	elif include_guide:
		content = build_promotion_configuration_guide()
	else:
		return None

	sources = [
		{
			"type": "erpnext",
			"name": "POS Promotion",
			"title": _("POS Promotion"),
			"summary": _("Live promotion catalog and configuration rules from ERPNext"),
			"url": "/app/pos-promotion",
		}
	]
	return content, "Live Data", "POS Promotion", sources, False
