# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from html import escape as html_escape

import frappe
from frappe import _
from frappe.utils import now_datetime, sanitize_html

from printechs_support.printechs_support_system.api.ticket_workflow import derive_workflow_routing_for_status


_TERMINAL_TICKET_STATUSES = frozenset({"Resolved", "Closed", "Cancelled"})


def auto_resolve_support_tickets_past_deadline():
	"""Mark tickets Resolved when customer confirmation window expired (hourly scheduler)."""
	now = now_datetime()
	rows = frappe.get_all(
		"Support Ticket",
		filters={
			"customer_resolution_deadline": ["<", now],
			"status": ["not in", list(_TERMINAL_TICKET_STATUSES)],
		},
		fields=["name", "status"],
	)
	for row in rows:
		name = row.name
		old = row.status
		ar, cot = derive_workflow_routing_for_status("Resolved")
		frappe.db.set_value(
			"Support Ticket",
			name,
			{
				"status": "Resolved",
				"action_required_from": ar,
				"current_owner_type": cot,
				"customer_resolution_deadline": None,
				"customer_confirmation_required": 0,
			},
		)
		doc = frappe.get_doc("Support Ticket", name)
		prev = frappe.flags.ignore_permissions
		frappe.flags.ignore_permissions = True
		try:
			doc.append(
				"comments",
				{
					"comment_type": "System Update",
					"comment_by": "Administrator",
					"comment_on": frappe.utils.now(),
					"is_customer_visible": 1,
					"content": sanitize_html(
						_(
							"<p><strong>Status</strong> updated from <em>{0}</em> to <em>Resolved</em> "
							"(confirmation period ended without customer response).</p>"
						).format(html_escape(old))
					),
				},
			)
			doc.save()
		finally:
			frappe.flags.ignore_permissions = prev


def daily():
	from printechs_support.printechs_support_system.api.agreement_portal import mark_expired_support_agreements
	from printechs_support.printechs_support_system.api.support import send_daily_task_reminders

	mark_expired_support_agreements()
	send_daily_task_reminders()


def hourly():
	auto_resolve_support_tickets_past_deadline()
	from printechs_support.printechs_support_system.api.support import update_overdue_flags

	update_overdue_flags()
