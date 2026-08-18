# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

PRAI_STUDIO_DOCTYPES = (
	"PRAI Source Project",
	"PRAI Source Scan Run",
	"PRAI Studio Knowledge Run",
	"PRAI Studio Health Rule Template",
	"PRAI Publish Log",
)

PRAI_STUDIO_ROLES = (
	{"role_name": "PRAI Studio Developer", "desk_access": 1},
	{"role_name": "PRAI Studio Manager", "desk_access": 1},
)


def ensure_prai_studio_roles() -> None:
	for row in PRAI_STUDIO_ROLES:
		if frappe.db.exists("Role", row["role_name"]):
			continue
		frappe.get_doc({"doctype": "Role", **row}).insert(ignore_permissions=True)


def _add_perm(doctype: str, role: str, **perms: int) -> None:
	if frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
		"name",
	):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			"if_owner": 0,
			**perms,
		}
	)
	doc.insert(ignore_permissions=True)
	validate_permissions_for_doctype(doctype)


def ensure_prai_studio_permissions() -> None:
	"""Role matrix for PRAI Studio Phase 1."""
	ensure_prai_studio_roles()
	full = dict(read=1, write=1, create=1, delete=1, export=1, print=1, email=1, report=1, share=1)
	upload = dict(read=1, write=1, create=1, delete=0, export=1, print=1, email=1, report=1, share=1)
	review = dict(read=1, write=1, create=0, delete=0, export=1, print=1, email=1, report=1, share=1)
	readonly = dict(read=1, write=0, create=0, delete=0, export=1, print=1, email=1, report=1, share=0)

	for dt in PRAI_STUDIO_DOCTYPES:
		_add_perm(dt, "System Manager", **full)
		_add_perm(dt, "PRAI Studio Developer", **upload)
		_add_perm(dt, "PRAI Studio Manager", **full)
		_add_perm(dt, "Printechs Support Coordinator", **full)
		_add_perm(dt, "Printechs Support Engineer", **review)
		_add_perm(dt, "Support Team", **readonly)


def user_can_upload_source() -> bool:
	user = frappe.session.user
	if user == "Guest":
		return False
	roles = set(frappe.get_roles(user))
	return bool(
		roles
		& {
			"System Manager",
			"PRAI Studio Developer",
			"PRAI Studio Manager",
			"Printechs Support Coordinator",
		}
	)


def user_can_review_studio() -> bool:
	user = frappe.session.user
	if user == "Guest":
		return False
	roles = set(frappe.get_roles(user))
	return bool(
		roles
		& {
			"System Manager",
			"PRAI Studio Manager",
			"Printechs Support Coordinator",
		}
	)


def user_can_publish_studio() -> bool:
	return user_can_review_studio()
