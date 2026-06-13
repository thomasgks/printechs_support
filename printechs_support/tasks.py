# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from html import escape as html_escape

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime, sanitize_html

from printechs_support.printechs_support_system.api.ticket_workflow import derive_workflow_routing_for_status


_TERMINAL_TICKET_STATUSES = frozenset({"Resolved", "Closed", "Cancelled"})
_DEFAULT_AUTO_CLOSE_RESOLVED_DAYS = 7


def auto_resolve_support_tickets_past_deadline():
	"""Mark tickets Resolved when customer confirmation window expired (hourly scheduler)."""
	now = now_datetime()
	rows = frappe.db.sql(
		"""
		SELECT st.name, st.status
		FROM `tabSupport Ticket` st
		WHERE st.customer_resolution_deadline < %(now)s
			AND IFNULL(st.customer_confirmation_required, 0) = 1
			AND st.action_required_from = 'Customer'
			AND st.status NOT IN %(terminal_statuses)s
			AND (
				IFNULL(st.team, '') != ''
				OR IFNULL(st.assigned_to, '') != ''
				OR EXISTS (
					SELECT 1
					FROM `tabSupport Ticket Assignee` ta
					WHERE ta.parent = st.name
						AND ta.parenttype = 'Support Ticket'
						AND IFNULL(ta.user, '') != ''
				)
			)
			AND (st.due_date IS NOT NULL OR st.resolution_due IS NOT NULL)
			AND (
				st.last_technician_reply_on IS NOT NULL
				OR st.last_internal_update_on IS NOT NULL
				OR st.resolved_on IS NOT NULL
			)
		""",
		{"now": now, "terminal_statuses": tuple(_TERMINAL_TICKET_STATUSES)},
		as_dict=True,
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
				"resolved_on": now,
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


def _auto_close_resolved_after_days() -> int:
	try:
		value = frappe.db.get_single_value(
			"Printechs Support Settings",
			"auto_close_resolved_after_days",
		)
	except Exception:
		return _DEFAULT_AUTO_CLOSE_RESOLVED_DAYS
	if value in (None, ""):
		return _DEFAULT_AUTO_CLOSE_RESOLVED_DAYS
	return max(cint(value), 0)


def auto_close_resolved_support_tickets_past_deadline():
	"""Mark long-resolved tickets Closed after the configured quiet period."""
	days = _auto_close_resolved_after_days()
	if days <= 0:
		return

	now = now_datetime()
	cutoff = add_to_date(now, days=-days)
	rows = frappe.db.sql(
		"""
		SELECT st.name, st.resolved_on
		FROM `tabSupport Ticket` st
		WHERE st.status = 'Resolved'
			AND st.resolved_on IS NOT NULL
			AND st.resolved_on < %(cutoff)s
			AND st.closed_on IS NULL
		""",
		{"cutoff": cutoff},
		as_dict=True,
	)
	for row in rows:
		name = row.name
		ar, cot = derive_workflow_routing_for_status("Closed")
		frappe.db.set_value(
			"Support Ticket",
			name,
			{
				"status": "Closed",
				"action_required_from": ar,
				"current_owner_type": cot,
				"closed_on": now,
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
							"<p><strong>Status</strong> updated from <em>Resolved</em> to <em>Closed</em> "
							"(auto-closed after {0} day(s) without further activity).</p>"
						).format(days)
					),
				},
			)
			doc.save()
		finally:
			frappe.flags.ignore_permissions = prev


def daily():
	from printechs_support.printechs_support_system.api.agreement_portal import mark_expired_support_agreements
	from printechs_support.printechs_support_system.api.pending_ticket_report_email import (
		send_pending_ticket_sla_report_if_due,
	)
	from printechs_support.printechs_support_system.api.support import send_daily_task_reminders

	mark_expired_support_agreements()
	send_daily_task_reminders()
	try:
		send_pending_ticket_sla_report_if_due()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Pending Ticket SLA Report Email")


def hourly():
	auto_resolve_support_tickets_past_deadline()
	auto_close_resolved_support_tickets_past_deadline()
	from printechs_support.printechs_support_system.api.support import update_overdue_flags

	update_overdue_flags()
