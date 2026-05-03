# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Format Frappe ``Version`` rows for the support portal (Desk edit history)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr


def _shorten(val: Any, max_len: int = 200) -> str:
	if val is None:
		return ""
	s = cstr(val).strip()
	if len(s) <= max_len:
		return s
	return s[: max_len - 1] + "…"


def format_version_row_for_portal(row: dict[str, Any], ref_meta) -> dict[str, Any]:
	"""Build a portal-safe dict for one ``Version`` row (from ``get_all`` fields)."""
	data_raw = row.get("data")
	try:
		data = json.loads(data_raw) if data_raw else {}
	except Exception:
		data = {}

	owner = (row.get("owner") or "").strip()
	creation = row.get("creation")
	version_name = row.get("name") or ""
	full_name = frappe.db.get_value("User", owner, "full_name") or owner

	changes: list[dict[str, str]] = []

	for row in data.get("changed") or []:
		if not row or len(row) < 3:
			continue
		fn, old, new = row[0], row[1], row[2]
		try:
			label = ref_meta.get_label(fn) or fn
		except Exception:
			label = fn
		changes.append(
			{
				"fieldname": cstr(fn),
				"label": cstr(label),
				"old": _shorten(old),
				"new": _shorten(new),
			}
		)

	for entry in data.get("row_changed") or []:
		if not entry or len(entry) < 4:
			continue
		table_field, row_idx, _row_name, child_changes = entry[0], entry[1], entry[2], entry[3]
		try:
			tlabel = ref_meta.get_label(table_field) or table_field
		except Exception:
			tlabel = table_field
		child_doctype = None
		try:
			df = ref_meta.get_field(table_field)
			child_doctype = df.options if df else None
		except Exception:
			child_doctype = None
		cm = frappe.get_meta(child_doctype) if child_doctype else None
		for ch in child_changes or []:
			if not ch or len(ch) < 3:
				continue
			cfn, cold, cnew = ch[0], ch[1], ch[2]
			try:
				clabel = cm.get_label(cfn) if cm else cfn
			except Exception:
				clabel = cfn
			ri = int(row_idx) if row_idx is not None else 0
			changes.append(
				{
					"fieldname": f"{table_field}.{cfn}",
					"label": _("{0} — row {1} — {2}").format(tlabel, ri + 1, clabel),
					"old": _shorten(cold),
					"new": _shorten(cnew),
				}
			)

	for added in data.get("added") or []:
		if len(added) < 2:
			continue
		tf, _row = added[0], added[1]
		try:
			tlabel = ref_meta.get_label(tf) or tf
		except Exception:
			tlabel = tf
		changes.append(
			{
				"fieldname": tf,
				"label": tlabel,
				"old": "",
				"new": _("Row added"),
			}
		)

	for removed in data.get("removed") or []:
		if len(removed) < 2:
			continue
		tf, _row = removed[0], removed[1]
		try:
			tlabel = ref_meta.get_label(tf) or tf
		except Exception:
			tlabel = tf
		changes.append(
			{
				"fieldname": tf,
				"label": tlabel,
				"old": _("Row removed"),
				"new": "",
			}
		)

	return {
		"name": cstr(version_name),
		"at": str(creation) if creation else None,
		"user": owner,
		"user_full_name": full_name,
		"changes": changes,
		"impersonated_by": data.get("impersonated_by"),
	}
