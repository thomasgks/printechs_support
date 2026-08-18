# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Email notifications when Support Tasks are created or assignees change."""

from __future__ import annotations

from html import escape as html_escape

import frappe
from frappe import _
from frappe.utils import strip_html

from printechs_support.printechs_support_system.api.ticket_comment_emails import (
	_collect_customer_portal_contact_emails,
	_collect_task_assignee_emails,
	_collect_task_team_emails,
	_portal_task_url,
	_portal_ticket_url,
	_ticket_customer_label,
	_user_email,
)




def _description_for_email_html(description: str | None, *, max_chars: int = 2000) -> str:
	raw = strip_html(description or "").strip()
	if not raw:
		return f'<span style="color:#94a3b8;font-style:italic;">{html_escape(_("No description provided."))}</span>'
	s = html_escape(raw)
	if len(s) > max_chars:
		s = s[: max_chars - 1] + "…"
	return s.replace("\n", "<br/>")


def _task_alert_html(
	*,
	title: str,
	intro: str,
	task_name: str,
	task_subject: str,
	ticket_name: str | None,
	customer_name: str,
	responsible_side: str,
	status: str,
	due_display: str,
	description_html: str,
	link: str,
	ticket_link: str | None,
	for_customer: bool,
) -> str:
	ticket_block = ""
	if ticket_name:
		ticket_block = f"""<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Ticket"))}</td><td style="padding:4px 8px;"><strong>{html_escape(ticket_name)}</strong></td></tr>"""

	extra_links = ""
	if ticket_link and not for_customer:
		extra_links = f"""<p style="margin:8px 0 0;"><a href="{html_escape(ticket_link)}" style="color:#4f46e5;">{html_escape(_("View parent ticket"))}</a></p>"""

	return f"""<div style="font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#1e293b;line-height:1.5;max-width:560px;">
<p style="margin:0 0 12px;font-size:16px;font-weight:600;color:#0f172a;">{html_escape(title)}</p>
<p style="margin:0 0 12px;">{html_escape(intro)}</p>
<table style="border-collapse:collapse;width:100%;margin:12px 0 16px;font-size:13px;">
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Task"))}</td><td style="padding:4px 8px;"><strong>{html_escape(task_name)}</strong></td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Subject"))}</td><td style="padding:4px 8px;">{html_escape(task_subject)}</td></tr>
{ticket_block}
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Customer"))}</td><td style="padding:4px 8px;"><strong>{html_escape(customer_name or "—")}</strong></td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Responsible side"))}</td><td style="padding:4px 8px;">{html_escape(responsible_side or "—")}</td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Status"))}</td><td style="padding:4px 8px;">{html_escape(status or "—")}</td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Due date"))}</td><td style="padding:4px 8px;">{html_escape(due_display or "—")}</td></tr>
</table>
<p style="margin:0 0 8px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;">{html_escape(_("Description"))}</p>
<p style="margin:0 0 12px;border:1px solid #e2e8f0;border-radius:8px;padding:12px;background:#f8fafc;">{description_html}</p>
<p style="margin:0;"><a href="{html_escape(link)}" style="color:#4f46e5;font-weight:600;">{html_escape(_("Open in support portal"))}</a></p>
{extra_links}
</div>"""


def _due_display(task) -> str:
	due = getattr(task, "due_date", None)
	if not due:
		return ""
	try:
		from frappe.utils import format_datetime, get_datetime

		return format_datetime(get_datetime(due))
	except Exception:
		return str(due)


def _should_notify_customer(task, ticket) -> bool:
	if not ticket:
		return False
	rs = (getattr(task, "responsible_side", None) or "Printechs").strip()
	if rs in ("Customer", "Shared"):
		return True
	# Ticket-linked tasks are visible in the customer portal — notify on create.
	return bool(getattr(task, "support_ticket", None))


def notify_support_task_created(task_name: str, *, actor: str | None = None) -> None:
	"""Email assignees and (when applicable) the customer after a Support Task is created."""
	if getattr(frappe.flags, "in_test", False):
		return
	if getattr(frappe.flags, "skip_task_creation_notification", False):
		return

	try:
		task = frappe.get_doc("Support Task", task_name)
	except Exception:
		return

	ticket = None
	ticket_name = (task.support_ticket or "").strip()
	if ticket_name:
		try:
			ticket = frappe.get_doc("Support Ticket", ticket_name)
		except Exception:
			ticket = None

	actor = (actor or frappe.session.user or "").strip()
	actor_em = _user_email(actor)
	task_subject = (task.subject or task_name).strip()
	customer_name = _ticket_customer_label(ticket) if ticket else ""
	link = _portal_task_url(task_name)
	ticket_link = _portal_ticket_url(ticket_name) if ticket_name else None
	desc_html = _description_for_email_html(getattr(task, "description", None))
	due_display = _due_display(task)
	rs = (task.responsible_side or "Printechs").strip()
	status = (task.status or "Open").strip()
	team_emails = _collect_task_team_emails(task, ticket)
	customer_emails = _collect_customer_portal_contact_emails(ticket) if ticket and _should_notify_customer(task, ticket) else []

	# Assignees (+ ticket team when linked), excluding creator when possible.
	team_to = [e for e in team_emails if e != actor_em]
	if not team_to and team_emails:
		team_to = list(team_emails)
	if team_to:
		subj = _("[{0}] New support task — {1}").format(task_name, task_subject)
		msg = _task_alert_html(
			title=_("New support task"),
			intro=_("A new support task was created and may require your attention."),
			task_name=task_name,
			task_subject=task_subject,
			ticket_name=ticket_name or None,
			customer_name=customer_name,
			responsible_side=rs,
			status=status,
			due_display=due_display,
			description_html=desc_html,
			link=link,
			ticket_link=ticket_link,
			for_customer=False,
		)
		_send(task_name, team_to, subj, msg)

	customer_to = [e for e in customer_emails if e != actor_em]
	if customer_to:
		subj_c = _("New support task on ticket {0}").format(ticket_name or task_name)
		msg_c = _task_alert_html(
			title=_("New task on your support ticket"),
			intro=_("Your support team has created a task linked to your ticket."),
			task_name=task_name,
			task_subject=task_subject,
			ticket_name=ticket_name or None,
			customer_name=customer_name,
			responsible_side=rs,
			status=status,
			due_display=due_display,
			description_html=desc_html,
			link=link,
			ticket_link=None,
			for_customer=True,
		)
		_send(task_name, customer_to, subj_c, msg_c)


def notify_support_task_new_assignees(
	task_name: str,
	*,
	new_assignee_users: set[str],
	actor: str | None = None,
) -> None:
	"""Email users newly added as task assignees (portal assignment after create, or Desk edit)."""
	if getattr(frappe.flags, "in_test", False):
		return
	if not new_assignee_users:
		return

	try:
		task = frappe.get_doc("Support Task", task_name)
	except Exception:
		return

	actor = (actor or frappe.session.user or "").strip()
	actor_em = _user_email(actor)
	recipients: set[str] = set()
	for uid in new_assignee_users:
		if uid and uid != actor:
			e = _user_email(uid)
			if e:
				recipients.add(e)
	if not recipients and new_assignee_users:
		for uid in new_assignee_users:
			e = _user_email(uid)
			if e:
				recipients.add(e)
	if not recipients:
		return

	ticket_name = (task.support_ticket or "").strip()
	task_subject = (task.subject or task_name).strip()
	link = _portal_task_url(task_name)
	ticket_link = _portal_ticket_url(ticket_name) if ticket_name else None
	subj = _("[{0}] You were assigned — {1}").format(task_name, task_subject)
	msg = _task_alert_html(
		title=_("Task assignment"),
		intro=_("You have been assigned to this support task."),
		task_name=task_name,
		task_subject=task_subject,
		ticket_name=ticket_name or None,
		customer_name="",
		responsible_side=(task.responsible_side or "Printechs").strip(),
		status=(task.status or "Open").strip(),
		due_display=_due_display(task),
		description_html=_description_for_email_html(getattr(task, "description", None)),
		link=link,
		ticket_link=ticket_link,
		for_customer=False,
	)
	_send(task_name, sorted(recipients), subj, msg)


def notify_support_task_due_date_changed(
	task_name: str,
	*,
	old_due,
	new_due,
	actor: str | None = None,
) -> None:
	"""Email task assignees when the due date changes."""
	if getattr(frappe.flags, "in_test", False):
		return
	if getattr(frappe.flags, "skip_task_due_date_notification", False):
		return

	try:
		task = frappe.get_doc("Support Task", task_name)
	except Exception:
		return

	from printechs_support.due_date_conversation_log import format_due_for_comment

	old_s = format_due_for_comment(old_due)
	new_s = format_due_for_comment(new_due)
	if old_s == new_s:
		return

	actor = (actor or frappe.session.user or "").strip()
	actor_em = _user_email(actor)
	recipients = [e for e in _collect_task_assignee_emails(task) if e != actor_em]
	if not recipients:
		recipients = _collect_task_assignee_emails(task)
	if not recipients:
		return

	ticket_name = (task.support_ticket or "").strip()
	task_subject = (task.subject or task_name).strip()
	link = _portal_task_url(task_name)
	ticket_link = _portal_ticket_url(ticket_name) if ticket_name else None
	subj = _("[{0}] Due date updated — {1}").format(task_name, task_subject)
	body = _task_alert_html(
		title=_("Task due date updated"),
		intro=_("The due date on this support task was changed to {0} (previously {1}).").format(new_s, old_s),
		task_name=task_name,
		task_subject=task_subject,
		ticket_name=ticket_name or None,
		customer_name="",
		responsible_side=(task.responsible_side or "Printechs").strip(),
		status=(task.status or "Open").strip(),
		due_display=new_s,
		description_html=_description_for_email_html(getattr(task, "description", None)),
		link=link,
		ticket_link=ticket_link,
		for_customer=False,
	)
	_send(task_name, recipients, subj, body)


def _send(task_name: str, recipients: list[str], subject: str, message: str) -> None:
	recipients = [r for r in recipients if r]
	if not recipients:
		return
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype="Support Task",
			reference_name=task_name,
			delayed=False,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Support Task alert email")
