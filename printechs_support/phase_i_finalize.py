# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Idempotent Phase I desk extras: portal menu sync, docperm fix, number cards, notifications."""

import json
import textwrap

import frappe

from printechs_support.setup_support_extras import ensure_acknowledgement_notification

# Bumped when the assignment email layout changes (existing Notification rows are updated).
SUPPORT_TICKET_ASSIGNED_EMAIL_VERSION = "printechs-assigned-email-v2"


def _fix_customer_docperm_if_owner():
	frappe.db.sql(
		"""
		UPDATE `tabCustom DocPerm`
		SET if_owner = 0
		WHERE parent IN ('Support Ticket', 'Support Task')
			AND role = 'Printechs Support Customer'
		"""
	)


def _ensure_number_card(name: str, label: str, filters: list) -> None:
	if frappe.db.exists("Number Card", name):
		return
	doc = frappe.new_doc("Number Card")
	doc.name = name
	doc.label = label
	doc.type = "Document Type"
	doc.document_type = "Support Ticket"
	doc.function = "Count"
	doc.filters_json = json.dumps(filters)
	doc.module = "Printechs Support System"
	doc.is_standard = 0
	doc.insert(ignore_permissions=True)


def _assignment_notification_message() -> str:
	return (
		f"<!-- {SUPPORT_TICKET_ASSIGNED_EMAIL_VERSION} -->\n"
		+ textwrap.dedent(
			"""
			<p>Hello,</p>
			<p>You have been assigned to support ticket <b>{{ doc.name }}</b>.</p>
			<ul>
			<li><b>Subject:</b> {{ doc.subject }}</li>
			<li><b>Customer:</b> {{ doc.customer_name or doc.customer }}</li>
			</ul>
			{{ doc.get_acknowledgement_description_block_html()|safe }}
			<p><a href="{{ doc.get_support_portal_ticket_url() }}">Open in support portal</a></p>
			<p>— Printechs Support</p>
			"""
		).strip()
	)


def _ensure_assignment_notification() -> None:
	name = "Support Ticket Assigned"
	expected_subj = "Printechs Support: ticket #{{ doc.name }}# assigned to you"
	body = _assignment_notification_message()

	def _apply_fields(doc):
		doc.subject = expected_subj
		doc.message = body
		if doc.meta.has_field("message_type"):
			doc.message_type = "HTML"

	if frappe.db.exists("Notification", name):
		n = frappe.get_doc("Notification", name)
		changed = False
		if n.subject != expected_subj:
			changed = True
		if SUPPORT_TICKET_ASSIGNED_EMAIL_VERSION not in (n.message or ""):
			changed = True
		if n.meta.has_field("message_type") and (n.message_type or "") != "HTML":
			changed = True
		if changed:
			_apply_fields(n)
			n.save(ignore_permissions=True)
		return
	n = frappe.new_doc("Notification")
	n.name = name
	n.document_type = "Support Ticket"
	n.event = "Value Change"
	n.channel = "Email"
	n.enabled = 1
	n.is_standard = 0
	n.value_changed = "assigned_to"
	n.condition = "doc.assigned_to"
	_apply_fields(n)
	n.append("recipients", {"receiver_by_document_field": "assigned_to"})
	n.insert(ignore_permissions=True)


def run_phase_i_finalize() -> None:
	ensure_acknowledgement_notification()
	_fix_customer_docperm_if_owner()
	_ensure_number_card("Open Support Tickets", "Open Support Tickets", [["status", "=", "Open"]])
	_ensure_number_card(
		"Overdue Support Tickets",
		"Overdue Support Tickets",
		[["is_overdue", "=", 1], ["status", "not in", ["Resolved", "Closed", "Cancelled"]]],
	)
	_ensure_assignment_notification()
	frappe.db.commit()
