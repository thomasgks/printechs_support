# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Expo push notifications for portal customers (Support Ticket updates)."""

from __future__ import annotations

import json
import logging

import frappe
from frappe import _
from frappe.integrations.utils import make_post_request
from frappe.utils import strip_html

from printechs_support.permissions import (
	get_allowed_customers,
	user_can_access_support_portal,
	user_sees_all_support_records,
)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_BATCH = 100

# Uses stdlib logging so messages appear in bench ``logs/web.log`` (gunicorn root handler).
_push_log = logging.getLogger("printechs_support.push")


def _norm_email(addr: str | None) -> str | None:
	if not addr or not str(addr).strip():
		return None
	return str(addr).strip().lower()


def portal_customer_user_ids_for_ticket(ticket) -> list[str]:
	"""Portal customer users who may receive mobile alerts for this ticket.

	Uses the same customer scope as portal access: contact email, contact person,
	User Permissions on Customer, Contacts linked to Customer, Support Agreement
	portal rows — then keeps only non-internal users with Printechs Support Customer
	who are allowed this ticket's Customer.
	"""
	cust = getattr(ticket, "customer", None)
	users: set[str] = set()

	em = _norm_email(getattr(ticket, "contact_email", None))
	if em:
		for (uname,) in frappe.db.sql(
			"""
			SELECT name FROM `tabUser`
			WHERE enabled = 1 AND LOWER(TRIM(IFNULL(email, ''))) = %s
			""",
			(em,),
		):
			users.add(uname)

	cp = getattr(ticket, "contact_person", None)
	if cp:
		u = frappe.db.get_value("Contact", cp, "user")
		if u and frappe.db.get_value("User", u, "enabled"):
			users.add(u)

	if cust:
		for (uname,) in frappe.db.sql(
			"""
			SELECT up.user FROM `tabUser Permission` up
			INNER JOIN `tabUser` u ON u.name = up.user AND u.enabled = 1
			WHERE up.allow = 'Customer' AND up.for_value = %s
			""",
			(cust,),
		):
			users.add(uname)
		for (uname,) in frappe.db.sql(
			"""
			SELECT DISTINCT c.user FROM `tabContact` c
			INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name AND dl.parenttype = 'Contact'
				AND dl.link_doctype = 'Customer' AND dl.link_name = %s
			WHERE IFNULL(c.user, '') NOT IN ('', 'Guest')
			""",
			(cust,),
		):
			if frappe.db.get_value("User", uname, "enabled"):
				users.add(uname)
		for (uname,) in frappe.db.sql(
			"""
			SELECT DISTINCT pc.portal_user
			FROM `tabSupport Agreement Portal Contact` pc
			INNER JOIN `tabSupport Agreement` sa ON sa.name = pc.parent
			WHERE sa.customer = %s AND IFNULL(pc.portal_user, '') != ''
			""",
			(cust,),
		):
			if frappe.db.get_value("User", uname, "enabled"):
				users.add(uname)

	out: list[str] = []
	for uid in users:
		if uid == "Guest":
			continue
		if user_sees_all_support_records(uid):
			continue
		if not user_can_access_support_portal(uid):
			continue
		if "Printechs Support Customer" not in frappe.get_roles(uid):
			continue
		if cust and cust not in get_allowed_customers(uid):
			continue
		out.append(uid)

	return list(dict.fromkeys(out))


def send_expo_push_to_users(
	user_ids: list[str],
	*,
	title: str,
	body: str,
	data: dict,
	ticket_name: str | None = None,
) -> None:
	"""POST to Expo; no-op if no tokens. Logs to standard logging (see bench logs/web.log)."""
	if getattr(frappe.flags, "in_test", False):
		return
	_push_log.info(
		"Printechs push: start ticket=%s user_ids=%s",
		ticket_name,
		user_ids,
	)
	if not user_ids:
		_push_log.warning(
			"Printechs push: skip (no portal users) ticket=%s — check Customer, contact, User Permission, Printechs Support Customer role",
			ticket_name,
		)
		return

	tokens: list[tuple[str, str]] = []
	for uid in user_ids:
		try:
			tok = frappe.db.get_value("User", uid, "printechs_expo_push_token")
		except Exception:
			tok = None
		if tok and str(tok).strip():
			tokens.append((uid, str(tok).strip()))

	if not tokens:
		_push_log.warning(
			"Printechs push: skip (no Expo tokens) ticket=%s users=%s — mobile must call register_mobile_push_token after login",
			ticket_name,
			user_ids,
		)
		return

	payload_data = {k: (str(v) if v is not None else "") for k, v in (data or {}).items()}
	msgs: list[dict] = []
	for _uid, token in tokens:
		msgs.append(
			{
				"to": token,
				"title": (title or "")[:200],
				"body": (body or "")[:400],
				"data": payload_data,
				"sound": "default",
			}
		)

	for i in range(0, len(msgs), _BATCH):
		chunk = msgs[i : i + _BATCH]
		try:
			resp = make_post_request(
				EXPO_PUSH_URL,
				json={"messages": chunk},
				headers={"Accept": "application/json", "Content-Type": "application/json"},
			)
			_push_log.info(
				"Printechs push: Expo OK ticket=%s messages=%s response=%s",
				ticket_name,
				len(chunk),
				json.dumps(resp)[:1500] if resp is not None else "null",
			)
			if isinstance(resp, dict):
				errors = resp.get("errors")
				if errors:
					frappe.log_error(
						message=json.dumps(errors)[:4000],
						title="Printechs Expo push API errors",
					)
				data_block = resp.get("data")
				if isinstance(data_block, list):
					for item in data_block:
						if isinstance(item, dict) and item.get("status") == "error":
							frappe.log_error(
								message=json.dumps(item)[:4000],
								title="Printechs Expo push ticket error",
							)
		except Exception:
			_push_log.exception("Printechs push: Expo HTTP failed ticket=%s", ticket_name)
			frappe.log_error(frappe.get_traceback(), "Printechs Expo push send")


def notify_customer_ticket_mobile_from_comment(
	ticket_name: str,
	*,
	subject_line: str,
	author_name: str,
	content_html: str,
	kind: str,
) -> None:
	"""Call when staff posted a customer-visible ticket thread row (same audience as email + portal scope)."""
	try:
		ticket = frappe.get_doc("Support Ticket", ticket_name)
	except Exception:
		return
	uids = portal_customer_user_ids_for_ticket(ticket)
	if not uids:
		_push_log.warning(
			"Printechs push: notify comment skipped (no portal users) ticket=%s customer=%s contact_email=%s",
			ticket_name,
			getattr(ticket, "customer", None),
			getattr(ticket, "contact_email", None),
		)
		return
	preview = strip_html(content_html or "").strip() or "—"
	body = f"{author_name}: {preview}"[:400]
	title = _("Update on {0}").format(ticket_name)
	send_expo_push_to_users(
		uids,
		title=title,
		body=body,
		data={"ticket_name": ticket_name, "type": "ticket_message", "kind": kind or ""},
		ticket_name=ticket_name,
	)


def notify_customer_new_ticket_mobile(ticket_name: str) -> None:
	"""When support opens a ticket on behalf of the customer (Desk / email), alert their app."""
	if getattr(frappe.flags, "in_test", False):
		return
	try:
		ticket = frappe.get_doc("Support Ticket", ticket_name)
	except Exception:
		return
	if (ticket.work_scope or "") != "Customer":
		return
	uids = portal_customer_user_ids_for_ticket(ticket)
	if not uids:
		return
	subj = ticket.subject or ticket_name
	title = _("New support ticket")
	desc_plain = strip_html(ticket.description or "").strip()
	body = f"{ticket_name} — {subj}"
	if desc_plain:
		body = f"{body} — {desc_plain}"
	body = body[:400]
	send_expo_push_to_users(
		uids,
		title=title,
		body=body,
		data={"ticket_name": ticket_name, "type": "new_ticket"},
		ticket_name=ticket_name,
	)
