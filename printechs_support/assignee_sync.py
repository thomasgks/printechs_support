# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Keep child-table assignees in sync with a single primary User link."""

import frappe
from frappe import _
from frappe.utils import cint


def sync_user_assignee_rows(doc, *, child_field: str, primary_field: str) -> None:
	"""One or more rows in ``child_field`` (User + is_primary); mirror primary to ``primary_field``."""
	rows = [r for r in (doc.get(child_field) or []) if getattr(r, "user", None)]

	if not rows and doc.get(primary_field):
		doc.append(child_field, {"user": doc.get(primary_field), "is_primary": 1})
		return

	if not rows:
		setattr(doc, primary_field, None)
		return

	users = [r.user for r in rows]
	if len(users) != len(set(users)):
		frappe.throw(_("Each user can appear only once in assignees."))

	prim = [r for r in rows if cint(r.is_primary)]
	if len(rows) == 1:
		rows[0].is_primary = 1
	elif not prim:
		rows[0].is_primary = 1
		for r in rows[1:]:
			r.is_primary = 0
	elif len(prim) > 1:
		first = prim[0]
		for r in rows:
			r.is_primary = 1 if r is first else 0

	primary = next((r for r in rows if cint(r.is_primary)), rows[0])
	setattr(doc, primary_field, primary.user)
