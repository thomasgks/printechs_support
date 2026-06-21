# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Email notifications when ticket thread comments are added (portal or Desk)."""

from __future__ import annotations

from html import escape as html_escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_url, strip_html


def _normalize_email(addr: str | None) -> str | None:
	if not addr or not str(addr).strip():
		return None
	try:
		from frappe.utils import validate_email_address

		s = str(addr).strip()
		validate_email_address(s, True)
		return s.lower()
	except Exception:
		return None


def _user_email(user_name: str | None) -> str | None:
	if not user_name:
		return None
	return _normalize_email(frappe.db.get_value("User", user_name, "email"))


def _collect_team_emails(ticket) -> list[str]:
	"""Team lead/default email + team members + ticket assignees (deduped)."""
	out: set[str] = set()
	team = getattr(ticket, "team", None)
	if team:
		row = frappe.db.get_value(
			"Support Team",
			team,
			["team_lead_email", "default_email"],
			as_dict=True,
		)
		if row:
			for key in ("team_lead_email", "default_email"):
				e = _normalize_email(row.get(key))
				if e:
					out.add(e)
		for member in frappe.get_all(
			"Support Team Member",
			filters={"parent": team, "parenttype": "Support Team"},
			pluck="user",
		):
			e = _user_email(member)
			if e:
				out.add(e)
	assigned = getattr(ticket, "assigned_to", None)
	if assigned:
		e = _user_email(assigned)
		if e:
			out.add(e)
	for row in getattr(ticket, "ticket_assignees", None) or []:
		u = row.get("user")
		if u:
			e = _user_email(u)
			if e:
				out.add(e)
	return sorted(out)


def _collect_customer_portal_contact_emails(ticket) -> list[str]:
	"""Support Agreement portal-contact emails for this ticket's customer."""
	out: set[str] = set()
	customer = getattr(ticket, "customer", None)
	if customer:
		rows = frappe.db.sql(
			"""
			SELECT DISTINCT pc.email
			FROM `tabSupport Agreement Portal Contact` pc
			INNER JOIN `tabSupport Agreement` sa ON sa.name = pc.parent
			WHERE sa.customer = %s
			  AND IFNULL(pc.email, '') != ''
			""",
			(customer,),
			as_dict=True,
		)
		for row in rows:
			e = _normalize_email(row.get("email"))
			if e:
				out.add(e)

	if not out:
		contact_em = _normalize_email(getattr(ticket, "contact_email", None))
		if contact_em:
			out.add(contact_em)
	return sorted(out)


def _portal_ticket_url(ticket_name: str) -> str:
	base = get_url().rstrip("/")
	return f"{base}/support-portal/tickets/{quote(ticket_name)}"


def _portal_task_url(task_name: str) -> str:
	base = get_url().rstrip("/")
	return f"{base}/support-portal/tasks/{quote(task_name)}"


def _collect_task_assignee_emails(task) -> list[str]:
	"""Primary + co-assignees on a Support Task."""
	out: set[str] = set()
	primary = getattr(task, "assigned_to_user", None)
	if primary:
		e = _user_email(primary)
		if e:
			out.add(e)
	for row in getattr(task, "task_assignees", None) or []:
		u = row.get("user") if isinstance(row, dict) else getattr(row, "user", None)
		if u:
			e = _user_email(u)
			if e:
				out.add(e)
	return sorted(out)


def _collect_task_team_emails(task, ticket=None) -> list[str]:
	"""Task assignees plus (when linked) ticket team / assignees."""
	out: set[str] = set()
	for e in _collect_task_assignee_emails(task):
		out.add(e)
	if ticket is not None:
		for e in _collect_team_emails(ticket):
			out.add(e)
	return sorted(out)


def _author_label(comment_by: str) -> str:
	if not comment_by:
		return _("Unknown")
	fn = frappe.db.get_value("User", comment_by, "full_name")
	return (fn or comment_by).strip()


def _strip_content_for_email(content_html: str, max_chars: int = 500) -> str:
	t = strip_html(content_html or "")
	t = t.strip()
	if not t:
		return "—"
	if len(t) > max_chars:
		return t[: max_chars - 1].rstrip() + "…"
	return t


def _ticket_customer_label(ticket) -> str:
	customer_name = (getattr(ticket, "customer_name", None) or "").strip()
	if customer_name:
		return customer_name
	customer = (getattr(ticket, "customer", None) or "").strip()
	if not customer:
		return ""
	return frappe.db.get_value("Customer", customer, "customer_name") or customer


def _email_activity_type(comment_type: str, *, author_is_internal: bool, is_internal_note: bool) -> str:
	"""Display-side activity label for email templates.

	The stored ``comment_type`` intentionally uses "Customer Reply" for customer-visible
	thread rows, including staff replies. Email recipients need the author side instead.
	"""
	kind = (comment_type or "").strip()
	if is_internal_note:
		return _("Internal note (not visible to customer)")
	if kind == "System Update":
		return _("System Update")
	if kind == "Reopen Issue":
		return _("Reopen Issue")
	if author_is_internal and kind in ("", "Comment", "Reply", "Customer Reply"):
		return _("Technician Reply")
	return kind or _("Comment")


def _email_author_role(*, author_is_internal: bool) -> str:
	return _("Technician") if author_is_internal else _("Customer")


def notify_ticket_comment(
	ticket_name: str,
	*,
	comment_type: str,
	comment_by: str,
	content_html: str,
	is_internal_note: bool,
	author_is_internal: bool,
	notify_team: bool = True,
) -> None:
	"""Notify customer and/or team when a ticket comment is posted.

	Rules:
	- Internal note: email team only (lead + assignees).
	- Customer-visible reply from staff: email customer portal contacts + team.
	- Customer-visible reply from customer: email team only (lead + assignees).
	- System updates (e.g. status): same as customer-visible from staff.
	"""
	if getattr(frappe.flags, "in_test", False):
		return

	try:
		ticket = frappe.get_doc("Support Ticket", ticket_name)
	except Exception:
		return

	customer_emails = _collect_customer_portal_contact_emails(ticket)
	team_emails = _collect_team_emails(ticket)
	author_em = _user_email(comment_by)
	subject_ticket = ticket.subject or ticket_name
	customer_name = _ticket_customer_label(ticket)
	author_name = _author_label(comment_by)
	body_preview = _strip_content_for_email(content_html)
	link = _portal_ticket_url(ticket_name)
	ticket_desc_html = ticket.get_acknowledgement_description_block_html()

	if is_internal_note:
		if not notify_team:
			return
		recipients = [e for e in team_emails if e != author_em]
		if not recipients:
			recipients = list(team_emails)
		if not recipients:
			return
		subj = _("[{0}] Internal note on {1}").format(ticket_name, subject_ticket)
		msg = _html_email(
			title=_("Internal note"),
			ticket_name=ticket_name,
			customer_name=customer_name,
			subject_line=subject_ticket,
			kind=_("Internal note (not visible to customer)"),
			author=author_name,
			author_role=_email_author_role(author_is_internal=True),
			body_text=body_preview,
			link=link,
		)
		_send_bulk(recipients, subj, msg, ticket_name)
		return

	# Customer-visible — status/system lines should always notify the customer when visible
	if comment_type == "System Update":
		author_is_internal = True
	email_kind = _email_activity_type(
		comment_type,
		author_is_internal=author_is_internal,
		is_internal_note=is_internal_note,
	)
	author_role = _email_author_role(author_is_internal=author_is_internal)

	if author_is_internal:
		customer_to = [e for e in customer_emails if e != author_em]
		team_to = [e for e in team_emails if e != author_em] if notify_team else []
		if customer_to:
			subj_c = _("Update on your support ticket {0}").format(ticket_name)
			msg_c = _html_email(
				title=_("New update on your ticket"),
				ticket_name=ticket_name,
				customer_name=customer_name,
				subject_line=subject_ticket,
				kind=email_kind,
				author=author_name,
				author_role=author_role,
				body_text=body_preview,
				link=link,
				for_customer=True,
			)
			_send_bulk(customer_to, subj_c, msg_c, ticket_name)
		# Mobile push: same staff→customer-visible case, even if email list was empty (e.g. missing contact_email) but Customer is set.
		if customer_to or getattr(ticket, "customer", None):
			try:
				from printechs_support.printechs_support_system.api.mobile_push import (
					notify_customer_ticket_mobile_from_comment,
				)

				notify_customer_ticket_mobile_from_comment(
					ticket_name,
					subject_line=subject_ticket,
					author_name=author_name,
					content_html=content_html,
					kind=comment_type or "",
				)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Support Ticket mobile push (comment)")
		if team_to:
			subj_t = _("[{0}] New reply — {1}").format(ticket_name, subject_ticket)
			msg_t = _html_email(
				title=_("New activity"),
				ticket_name=ticket_name,
				customer_name=customer_name,
				subject_line=subject_ticket,
				kind=email_kind,
				author=author_name,
				author_role=author_role,
				body_text=body_preview,
				link=link,
				for_customer=False,
				ticket_description_html=ticket_desc_html,
			)
			_send_bulk(team_to, subj_t, msg_t, ticket_name)
		return

	# Customer posted — notify team only
	if not notify_team:
		return
	team_to = [e for e in team_emails if e != author_em]
	if not team_to:
		return
	is_reopen = comment_type == "Reopen Issue"
	subj = (
		_("[{0}] Ticket reopened — {1}").format(ticket_name, subject_ticket)
		if is_reopen
		else _("[{0}] Customer reply — {1}").format(ticket_name, subject_ticket)
	)
	msg = _html_email(
		title=_("Ticket reopened by customer") if is_reopen else _("Customer reply"),
		ticket_name=ticket_name,
		customer_name=customer_name,
		subject_line=subject_ticket,
		kind=email_kind,
		author=author_name,
		author_role=_email_author_role(author_is_internal=False),
		body_text=body_preview,
		link=link,
		for_customer=False,
		ticket_description_html=ticket_desc_html,
	)
	_send_bulk(team_to, subj, msg, ticket_name)


def notify_task_comment(
	task_name: str,
	*,
	comment_type: str,
	comment_by: str,
	content_html: str,
	is_internal_note: bool,
	author_is_internal: bool,
	notify_team: bool = True,
) -> None:
	"""Notify customer and/or team when a Support Task comment is posted.

	Rules mirror :func:`notify_ticket_comment`, scoped to the task thread:
	- Internal note: email task assignees (+ ticket team when linked); never the customer.
	- Customer-visible reply from staff: email customer (when ticket linked) + team.
	- Customer-visible reply from customer: email team only.
	"""
	if getattr(frappe.flags, "in_test", False):
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

	team_emails = _collect_task_team_emails(task, ticket)
	customer_emails = _collect_customer_portal_contact_emails(ticket) if ticket else []
	author_em = _user_email(comment_by)
	task_subject = (task.subject or task_name).strip()
	author_name = _author_label(comment_by)
	body_preview = _strip_content_for_email(content_html)
	link = _portal_task_url(task_name)
	ticket_link = _portal_ticket_url(ticket_name) if ticket_name else ""
	customer_name = _ticket_customer_label(ticket) if ticket else ""
	ticket_desc_html = ticket.get_acknowledgement_description_block_html() if ticket else ""

	if is_internal_note:
		if not notify_team:
			return
		recipients = [e for e in team_emails if e != author_em]
		if not recipients:
			recipients = list(team_emails)
		if not recipients:
			return
		subj = _("[{0}] Internal note on task — {1}").format(task_name, task_subject)
		msg = _html_email(
			title=_("Internal note on task"),
			ticket_name=ticket_name or task_name,
			customer_name=customer_name,
			subject_line=task_subject,
			kind=_("Internal note (not visible to customer)"),
			author=author_name,
			author_role=_email_author_role(author_is_internal=True),
			body_text=body_preview,
			link=link,
			task_name=task_name,
			task_subject=task_subject,
			ticket_link=ticket_link or None,
		)
		_send_bulk(recipients, subj, msg, task_name, reference_doctype="Support Task")
		return

	if comment_type == "System Update":
		author_is_internal = True
	email_kind = _email_activity_type(
		comment_type,
		author_is_internal=author_is_internal,
		is_internal_note=is_internal_note,
	)
	author_role = _email_author_role(author_is_internal=author_is_internal)

	if author_is_internal:
		customer_to = [e for e in customer_emails if e != author_em]
		team_to = [e for e in team_emails if e != author_em] if notify_team else []
		if customer_to:
			subj_c = _("Update on support task {0}").format(task_name)
			msg_c = _html_email(
				title=_("New update on your task"),
				ticket_name=ticket_name or task_name,
				customer_name=customer_name,
				subject_line=task_subject,
				kind=email_kind,
				author=author_name,
				author_role=author_role,
				body_text=body_preview,
				link=link,
				for_customer=True,
				task_name=task_name,
				task_subject=task_subject,
				ticket_link=ticket_link or None,
			)
			_send_bulk(customer_to, subj_c, msg_c, task_name, reference_doctype="Support Task")
		if customer_to or (ticket and getattr(ticket, "customer", None)):
			try:
				from printechs_support.printechs_support_system.api.mobile_push import (
					notify_customer_ticket_mobile_from_comment,
				)

				if ticket_name:
					notify_customer_ticket_mobile_from_comment(
						ticket_name,
						subject_line=task_subject,
						author_name=author_name,
						content_html=content_html,
						kind=comment_type or "",
					)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Support Task mobile push (comment)")
		if team_to:
			subj_t = _("[{0}] New reply on task — {1}").format(task_name, task_subject)
			msg_t = _html_email(
				title=_("New task activity"),
				ticket_name=ticket_name or task_name,
				customer_name=customer_name,
				subject_line=task_subject,
				kind=email_kind,
				author=author_name,
				author_role=author_role,
				body_text=body_preview,
				link=link,
				for_customer=False,
				ticket_description_html=ticket_desc_html,
				task_name=task_name,
				task_subject=task_subject,
				ticket_link=ticket_link or None,
			)
			_send_bulk(team_to, subj_t, msg_t, task_name, reference_doctype="Support Task")
		return

	if not notify_team:
		return
	team_to = [e for e in team_emails if e != author_em]
	if not team_to:
		team_to = list(team_emails)
	if not team_to:
		return
	subj = _("[{0}] Customer reply on task — {1}").format(task_name, task_subject)
	msg = _html_email(
		title=_("Customer reply on task"),
		ticket_name=ticket_name or task_name,
		customer_name=customer_name,
		subject_line=task_subject,
		kind=email_kind,
		author=author_name,
		author_role=_email_author_role(author_is_internal=False),
		body_text=body_preview,
		link=link,
		for_customer=False,
		ticket_description_html=ticket_desc_html,
		task_name=task_name,
		task_subject=task_subject,
		ticket_link=ticket_link or None,
	)
	_send_bulk(team_to, subj, msg, task_name, reference_doctype="Support Task")


def _html_email(
	*,
	title: str,
	ticket_name: str,
	customer_name: str,
	subject_line: str,
	kind: str,
	author: str,
	author_role: str,
	body_text: str,
	link: str,
	for_customer: bool = False,
	ticket_description_html: str = "",
	task_name: str | None = None,
	task_subject: str | None = None,
	ticket_link: str | None = None,
) -> str:
	if task_name:
		intro = (
			_("Your support team has posted an update on this task.")
			if for_customer
			else _("There is new activity on this support task.")
		)
	else:
		intro = (
			_("Your support team has posted an update on this ticket.")
			if for_customer
			else _("There is new activity on this support ticket.")
		)

	task_rows = ""
	if task_name:
		task_rows = f"""<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Task"))}</td><td style="padding:4px 8px;"><strong>{html_escape(task_name)}</strong></td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Task subject"))}</td><td style="padding:4px 8px;">{html_escape(task_subject or subject_line)}</td></tr>"""

	ticket_row = ""
	if ticket_name and task_name:
		ticket_row = f"""<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Ticket"))}</td><td style="padding:4px 8px;"><strong>{html_escape(ticket_name)}</strong></td></tr>"""
	elif not task_name:
		ticket_row = f"""<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Ticket"))}</td><td style="padding:4px 8px;"><strong>{html_escape(ticket_name)}</strong></td></tr>"""

	subject_label = _("Task subject") if task_name else _("Subject")
	subject_value = (task_subject or subject_line) if task_name else subject_line
	subject_row = ""
	if not task_name:
		subject_row = f"""<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(subject_label)}</td><td style="padding:4px 8px;">{html_escape(subject_value)}</td></tr>"""

	extra_links = ""
	if ticket_link and task_name:
		extra_links = f"""<p style="margin:8px 0 0;"><a href="{html_escape(ticket_link)}" style="color:#4f46e5;">{html_escape(_("View parent ticket"))}</a></p>"""

	return f"""<div style="font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#1e293b;line-height:1.5;max-width:560px;">
<p style="margin:0 0 12px;font-size:16px;font-weight:600;color:#0f172a;">{html_escape(title)}</p>
<p style="margin:0 0 12px;">{html_escape(intro)}</p>
<table style="border-collapse:collapse;width:100%;margin:12px 0 16px;font-size:13px;">
{task_rows}{ticket_row}
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Customer"))}</td><td style="padding:4px 8px;"><strong>{html_escape(customer_name or "—")}</strong></td></tr>
{subject_row}
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Type"))}</td><td style="padding:4px 8px;">{html_escape(kind)}</td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("From"))}</td><td style="padding:4px 8px;">{html_escape(author)}</td></tr>
<tr><td style="padding:4px 8px;color:#64748b;">{html_escape(_("Message Type"))}</td><td style="padding:4px 8px;"><strong>{html_escape(author_role or "—")}</strong></td></tr>
</table>
{ticket_description_html or ""}
<p style="margin:0 0 8px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;">{html_escape(_("Message"))}</p>
<p style="margin:0 0 12px;white-space:pre-wrap;border:1px solid #e2e8f0;border-radius:8px;padding:12px;background:#f8fafc;">{html_escape(body_text)}</p>
<p style="margin:0;"><a href="{html_escape(link)}" style="color:#4f46e5;font-weight:600;">{html_escape(_("Open in support portal"))}</a></p>
{extra_links}
</div>"""


def _send_bulk(
	recipients: list[str],
	subject: str,
	message: str,
	reference_name: str,
	*,
	reference_doctype: str = "Support Ticket",
) -> None:
	recipients = [r for r in recipients if r]
	if not recipients:
		return
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			delayed=False,
		)
	except Exception:
		label = "Support Task comment email" if reference_doctype == "Support Task" else "Support Ticket comment email"
		frappe.log_error(frappe.get_traceback(), label)
