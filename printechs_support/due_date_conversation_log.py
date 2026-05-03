# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Append Support Ticket thread rows when ``due_date`` changes (portal audit trail).

Set ``LOG_DUE_DATE_IN_TICKET_CONVERSATION`` to False to disable without removing code.
"""

from __future__ import annotations

from html import escape as html_escape

import frappe
from frappe import _
from frappe.utils import format_datetime, now_datetime

# Flip to False to roll back conversation lines (Version history unchanged).
LOG_DUE_DATE_IN_TICKET_CONVERSATION = True

# Marker so SupportTicket.on_update can skip email for this row (see support_ticket.on_update).
# Customer-visible so portal conversation loads the row for all users (internal-only rows are hidden for customers).
_AUDIT_MARKER = 'data-printechs-audit="due-date"'


def format_due_for_comment(dt) -> str:
	if not dt:
		return str(_("(none)"))
	try:
		return format_datetime(dt)
	except Exception:
		return str(dt)


def _changed_by_html(user_id: str) -> str:
	"""Safe HTML snippet: full name + user id for audit trail."""
	fn = frappe.db.get_value("User", user_id, "full_name") or user_id
	return (
		f'<p><span class="text-slate-600">{_("Changed by")}:</span> '
		f"<strong>{html_escape(str(fn).strip() or user_id)}</strong> "
		f'<span class="text-slate-500">({html_escape(user_id)})</span></p>'
	)


def append_due_date_change_comment(doc, old_due, new_due) -> None:
	"""Append a System Update row to ``doc.comments`` (call from SupportTicket.validate)."""
	if not LOG_DUE_DATE_IN_TICKET_CONVERSATION:
		return
	user = frappe.session.user
	if not user or user == "Guest":
		user = "Administrator"
	old_s = format_due_for_comment(old_due)
	new_s = format_due_for_comment(new_due)
	by_html = _changed_by_html(user)
	doc.append(
		"comments",
		{
			"comment_type": "System Update",
			"comment_by": user,
			"comment_on": now_datetime(),
			"is_customer_visible": 1,
			"content": (
				f'<p {_AUDIT_MARKER}><strong>{_("Due date updated")}</strong></p>'
				f"{by_html}"
				f"<p>{_('Previous')}: {old_s}<br/>{_('New')}: {new_s}</p>"
			),
		},
	)
