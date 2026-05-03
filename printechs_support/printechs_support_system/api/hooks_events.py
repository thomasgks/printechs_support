# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import now_datetime


def support_ticket_on_update(doc, method=None):
	frappe.db.set_value(
		"Support Ticket",
		doc.name,
		"last_internal_update_on",
		now_datetime(),
		update_modified=False,
	)


def communication_after_insert(doc, method=None):
	"""When an email is received on a ticket thread, refresh last customer update time."""
	if doc.reference_doctype != "Support Ticket" or not doc.reference_name:
		return
	if getattr(doc, "communication_medium", None) != "Email":
		return
	if getattr(doc, "sent_or_received", None) != "Received":
		return
	frappe.db.set_value(
		"Support Ticket",
		doc.reference_name,
		"last_customer_update_on",
		doc.creation,
		update_modified=False,
	)
