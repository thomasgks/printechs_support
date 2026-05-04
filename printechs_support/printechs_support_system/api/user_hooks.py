import frappe
from frappe.utils import cint

from printechs_support.printechs_support_system.api.agreement_portal import (
	PORTAL_ROLE,
	send_portal_welcome_email,
)


def _has_portal_role(doc) -> bool:
	return any((row.role or "") == PORTAL_ROLE for row in (doc.roles or []))


def before_insert_user(doc, method=None) -> None:
	if not cint(doc.send_welcome_email) or not _has_portal_role(doc):
		return
	doc.flags.printechs_send_portal_welcome = 1
	doc.send_welcome_email = 0


def after_insert_user(doc, method=None) -> None:
	if not doc.flags.get("printechs_send_portal_welcome"):
		return
	try:
		send_portal_welcome_email(doc)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Printechs portal user welcome email")
