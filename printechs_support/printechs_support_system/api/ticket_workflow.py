# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Structured Support Ticket workflow: status transitions, next-action routing, audit log.

Portal and Desk should call these helpers rather than toggling ``status`` directly.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from printechs_support.permissions import (
	get_allowed_customers,
	user_sees_all_support_records,
)

WF_STATUSES = frozenset(
	{
		"Open",
		"Assigned",
		"In Progress",
		"Hold",
		"Waiting for Customer",
		"Waiting for Technician",
		"Reopened",
		"Resolved",
		"Closed",
		"Cancelled",
	}
)

WF_ACTION_FROM = frozenset({"Customer", "Technician", "Manager", "None"})

# Coordinator / PM act as managers for assignment and closure policy.
_MANAGER_ROLES = frozenset(
	{
		"Printechs Support Coordinator",
		"Printechs Support Project Manager",
	}
)
def _internal_roles_set() -> frozenset:
	from printechs_support.permissions import _internal_roles

	return frozenset(_internal_roles())


def classify_actor_role_type(user: str) -> str:
	"""Return Customer | Technician | Manager | System for workflow logging."""
	if not user or user == "Guest":
		return "System"
	if user == "Administrator":
		return "System"
	roles = set(frappe.get_roles(user))
	internal = _internal_roles_set()
	if "Printechs Support Customer" in roles and not (internal & roles):
		return "Customer"
	if _MANAGER_ROLES & roles:
		return "Manager"
	if internal & roles:
		return "Technician"
	return "Technician"


def _doc_or_name(ticket_name: str):
	if hasattr(ticket_name, "doctype"):
		return ticket_name
	return frappe.get_doc("Support Ticket", ticket_name)


def derive_workflow_routing_for_status(status: str) -> tuple[str, str]:
	"""Map a target ``status`` to (``action_required_from``, ``current_owner_type``).

	Used when a status is set from the portal (e.g. internal “set status on send”) so
	:func:`validate_workflow_consistency` passes and the header shows the right “who acts next”.
	"""
	s = (status or "").strip()
	if s == "Waiting for Customer":
		return ("Customer", "Customer")
	if s == "Waiting for Technician":
		return ("Technician", "Technician")
	if s in ("In Progress", "Assigned", "Reopened"):
		return ("Technician", "Technician")
	if s == "Hold":
		return ("None", "None")
	if s == "Resolved":
		return ("Customer", "Customer")
	if s in ("Closed", "Cancelled"):
		return ("None", "None")
	if s == "Open":
		return ("Manager", "Manager")
	return ("Manager", "Manager")


def sync_waiting_side_fields(doc) -> None:
	"""Align legacy delay/wait fields with workflow status for SLA prep."""
	st = doc.status or ""
	ar = doc.action_required_from or ""
	if st == "Waiting for Customer":
		doc.waiting_for_side = "Customer"
	elif st == "Waiting for Technician":
		doc.waiting_for_side = "Printechs"
	elif st in ("Hold", "Resolved", "Closed", "Cancelled"):
		doc.waiting_for_side = "None"
	elif st == "Reopened":
		doc.waiting_for_side = "Printechs"
	if ar == "Customer":
		doc.delay_owner = "Customer"
	elif ar == "Technician":
		doc.delay_owner = "Printechs"
	elif ar == "Manager":
		doc.delay_owner = "Printechs"
	elif ar == "None":
		doc.delay_owner = "None"


def validate_workflow_consistency(doc) -> None:
	"""Best-effort consistency checks (allows admin override via flags)."""
	if getattr(doc.flags, "ignore_workflow_validation", False):
		return
	st = doc.status or ""
	ar = doc.action_required_from or ""

	if st == "Waiting for Customer" and ar not in ("Customer",):
		frappe.throw(
			_("When status is Waiting for Customer, Action Required From must be Customer."),
			frappe.ValidationError,
		)
	if st == "Waiting for Technician" and ar not in ("Technician",):
		frappe.throw(
			_("When status is Waiting for Technician, Action Required From must be Technician."),
			frappe.ValidationError,
		)
	if st == "Reopened" and ar not in ("Technician",):
		frappe.throw(
			_("When status is Reopened, Action Required From must be Technician."),
			frappe.ValidationError,
		)
	if st == "Resolved" and ar not in ("Customer", "None"):
		frappe.throw(
			_("When status is Resolved, Action Required From must be Customer or None."),
			frappe.ValidationError,
		)
	if st == "Hold" and ar != "None":
		frappe.throw(
			_("When status is Hold, Action Required From must be None."),
			frappe.ValidationError,
		)
	if st in ("Closed", "Cancelled") and ar != "None":
		frappe.throw(
			_("Closed or Cancelled tickets must have Action Required From = None."),
			frappe.ValidationError,
		)


def append_workflow_log(
	doc,
	*,
	user: str,
	reply_type: str,
	message: str | None = None,
	subject: str | None = None,
	is_internal: bool = False,
	attachment: str | None = None,
	prev_status: str | None = None,
	new_status: str | None = None,
	prev_action: str | None = None,
	new_action: str | None = None,
) -> None:
	"""Append one row to ``workflow_log`` (caller saves the document)."""
	role_type = classify_actor_role_type(user)
	doc.append(
		"workflow_log",
		{
			"posted_by": user,
			"posted_by_role_type": role_type,
			"is_internal": 1 if is_internal else 0,
			"reply_type": reply_type,
			"subject": subject or "",
			"message": message or "",
			"previous_status": prev_status or "",
			"new_status": new_status or "",
			"previous_action_required_from": prev_action or "",
			"new_action_required_from": new_action or "",
			"created_on": now_datetime(),
			"attachment": attachment or None,
		},
	)


def _save(
	doc,
	*,
	user: str,
	reply_type: str,
	message: str | None,
	is_internal: bool,
	prev_st: str,
	prev_ar: str,
	subject: str | None = None,
	attachment: str | None = None,
):
	append_workflow_log(
		doc,
		user=user,
		reply_type=reply_type,
		message=message,
		subject=subject,
		is_internal=is_internal,
		attachment=attachment,
		prev_status=prev_st,
		new_status=doc.status,
		prev_action=prev_ar,
		new_action=doc.action_required_from,
	)
	sync_waiting_side_fields(doc)
	doc.flags.workflow_transition = True
	try:
		doc.save()
	finally:
		doc.flags.workflow_transition = False


def _assert_terminal_policy(doc, allow_if_admin: bool = False) -> None:
	st = doc.status or ""
	if st == "Cancelled" and not allow_if_admin:
		frappe.throw(_("Cancelled tickets cannot be modified."), frappe.ValidationError)


def _assert_assignee(doc, user: str) -> None:
	"""Technician actions: assigned user or internal with ticket access."""
	if user_sees_all_support_records(user):
		if frappe.has_permission("Support Ticket", "write", doc):
			return
	r_primary = (doc.assigned_to or "").strip()
	if r_primary == user:
		return
	if frappe.db.exists("Support Ticket Assignee", {"parent": doc.name, "user": user}):
		return
	frappe.throw(_("You are not assigned to this ticket."), frappe.PermissionError)


def _assert_internal_or_assignee(doc, user: str) -> None:
	"""Desk/internal users may act; otherwise must be an assignee."""
	if user_sees_all_support_records(user):
		return
	_assert_assignee(doc, user)


def _assert_customer(doc, user: str) -> None:
	cust = doc.customer
	if not cust:
		frappe.throw(_("Ticket has no customer."), frappe.ValidationError)
	allowed = get_allowed_customers(user)
	if cust not in allowed:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _assert_manager(user: str) -> None:
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return
	if _MANAGER_ROLES & set(frappe.get_roles(user)):
		return
	frappe.throw(_("Only managers can perform this action."), frappe.PermissionError)


# --- Public workflow operations ---


def assign_ticket(
	ticket_name: str,
	technician_user: str,
	due_date=None,
	assigned_by: str | None = None,
	note: str | None = None,
) -> dict[str, Any]:
	"""Assign primary technician; status becomes Assigned."""
	doc = _doc_or_name(ticket_name)
	user = frappe.session.user
	if not frappe.has_permission("Support Ticket", "write", doc=doc):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not technician_user or not frappe.db.exists("User", technician_user):
		frappe.throw(_("Valid technician user is required."), frappe.ValidationError)
	_assert_terminal_policy(doc)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.assigned_to = technician_user
	doc.assigned_by = assigned_by or user
	doc.assigned_on = now_datetime()
	if due_date is not None:
		doc.due_date = due_date

	doc.status = "Assigned"
	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"

	_save(
		doc,
		user=user,
		reply_type="Assignment Update",
		message=note or _("Ticket assigned."),
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "name": doc.name, "status": doc.status, "action_required_from": doc.action_required_from}


def technician_send_acknowledgement(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	"""No mandatory status change; keeps technician ownership."""
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	# Optional: Open -> Assigned when primary technician acknowledges (still no customer wait).
	if prev_st == "Open" and doc.assigned_to == uid:
		doc.status = "Assigned"

	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"
	doc.last_technician_reply_on = now_datetime()
	doc.last_internal_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Acknowledgement",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def technician_start_work(ticket_name: str, message: str | None = None, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.status = "In Progress"
	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"
	if not doc.first_response_on:
		doc.first_response_on = now_datetime()
	doc.last_technician_reply_on = now_datetime()
	doc.last_internal_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Work Update",
		message=message or _("Work started."),
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def technician_request_customer_input(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.status = "Waiting for Customer"
	doc.action_required_from = "Customer"
	doc.current_owner_type = "Customer"
	doc.waiting_since = now_datetime()
	doc.last_technician_reply_on = now_datetime()
	doc.last_internal_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Request Customer Input",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def customer_acknowledgement(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_customer(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.last_customer_reply_on = now_datetime()
	doc.last_customer_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Acknowledgement",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def customer_informational_reply(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_customer(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.last_customer_reply_on = now_datetime()
	doc.last_customer_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Informational Reply",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def customer_provide_requested_information(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_customer(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	if prev_st == "Waiting for Customer":
		doc.status = "Waiting for Technician"
		doc.action_required_from = "Technician"
		doc.current_owner_type = "Technician"

	doc.last_customer_reply_on = now_datetime()
	doc.last_customer_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Provide Requested Information",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def customer_followup_question(
	ticket_name: str,
	message: str,
	user: str | None = None,
	*,
	reopen_from_resolved: bool = False,
) -> dict[str, Any]:
	"""Customer follow-up; optionally bump to Waiting for Technician / Reopened."""
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_customer(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	if prev_st == "Resolved" and reopen_from_resolved:
		doc.status = "Reopened"
		doc.action_required_from = "Technician"
		doc.current_owner_type = "Technician"
		doc.reopened_count = int(doc.reopened_count or 0) + 1
		doc.is_reopened = 1
	elif prev_st not in ("Closed", "Cancelled"):
		doc.status = "Waiting for Technician"
		doc.action_required_from = "Technician"
		doc.current_owner_type = "Technician"

	doc.last_customer_reply_on = now_datetime()
	doc.last_customer_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Ask Follow-up Question",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def technician_resume_after_customer_reply(
	ticket_name: str, message: str | None = None, user: str | None = None
) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	if prev_st in ("Waiting for Technician", "Reopened"):
		doc.status = "In Progress"
	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"
	doc.last_technician_reply_on = now_datetime()
	doc.last_internal_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Work Update",
		message=message or _("Resumed work."),
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def technician_send_work_update(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	"""Work update: from Waiting for Technician moves to In Progress; otherwise keeps stage sensible."""
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	if prev_st == "Waiting for Technician":
		doc.status = "In Progress"
	elif prev_st in ("Assigned", "Reopened"):
		doc.status = "In Progress"

	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"
	doc.last_technician_reply_on = now_datetime()
	doc.last_internal_update_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Work Update",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def technician_send_resolution(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.status = "Resolved"
	doc.action_required_from = "Customer"
	doc.current_owner_type = "Customer"
	doc.resolved_on = now_datetime()
	doc.last_technician_reply_on = now_datetime()
	doc.last_internal_update_on = now_datetime()
	if getattr(doc, "customer_confirmation_required", None) is not None:
		doc.customer_confirmation_required = 1

	_save(
		doc,
		user=uid,
		reply_type="Resolution",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def customer_confirm_resolved(ticket_name: str, message: str | None = None, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	if not user_sees_all_support_records(uid):
		_assert_customer(doc, uid)
	if (doc.status or "") != "Resolved":
		frappe.throw(_("You can only confirm when the ticket is Resolved."), frappe.ValidationError)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.status = "Closed"
	doc.action_required_from = "None"
	doc.current_owner_type = "None"
	doc.closed_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="Confirm Resolved",
		message=message or _("Confirmed resolved."),
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def manager_close_ticket(ticket_name: str, message: str | None = None, user: str | None = None) -> dict[str, Any]:
	"""Force-close from Resolved or other non-terminal states (manager)."""
	uid = user or frappe.session.user
	_assert_manager(uid)
	doc = _doc_or_name(ticket_name)
	_assert_terminal_policy(doc)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.status = "Closed"
	doc.action_required_from = "None"
	doc.current_owner_type = "None"
	doc.closed_on = now_datetime()

	_save(
		doc,
		user=uid,
		reply_type="System Status Update",
		message=message or _("Closed by manager."),
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def customer_reopen_issue(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_customer(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	if prev_st not in ("Resolved", "Closed"):
		frappe.throw(_("Ticket can only be reopened from Resolved or Closed."), frappe.ValidationError)

	doc.status = "Reopened"
	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"
	doc.reopened_count = int(doc.reopened_count or 0) + 1
	doc.is_reopened = 1

	_save(
		doc,
		user=uid,
		reply_type="Reopen Issue",
		message=message,
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	try:
		from printechs_support.printechs_support_system.api.ticket_comment_emails import notify_ticket_comment

		notify_ticket_comment(
			doc.name,
			comment_type="Reopen Issue",
			comment_by=uid,
			content_html=message,
			is_internal_note=False,
			author_is_internal=False,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Support Ticket reopen email")
	return {"ok": True, "status": doc.status}


def technician_internal_note(ticket_name: str, message: str, user: str | None = None) -> dict[str, Any]:
	doc = _doc_or_name(ticket_name)
	uid = user or frappe.session.user
	_assert_terminal_policy(doc)
	_assert_internal_or_assignee(doc, uid)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	_save(
		doc,
		user=uid,
		reply_type="Internal Note",
		message=message,
		is_internal=True,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


def cancel_ticket(ticket_name: str, reason: str | None = None, user: str | None = None) -> dict[str, Any]:
	uid = user or frappe.session.user
	doc = _doc_or_name(ticket_name)
	_assert_terminal_policy(doc)

	prev_st = doc.status
	prev_ar = doc.action_required_from

	doc.status = "Cancelled"
	doc.action_required_from = "None"
	doc.current_owner_type = "None"
	if reason:
		doc.pending_reason = reason

	_save(
		doc,
		user=uid,
		reply_type="System Status Update",
		message=reason or _("Cancelled."),
		is_internal=False,
		prev_st=prev_st,
		prev_ar=prev_ar,
	)
	return {"ok": True, "status": doc.status}


# --- Whitelisted API wrappers ---


@frappe.whitelist()
def wf_assign_ticket(ticket_name, technician_user, due_date=None, assigned_by=None, note=None):
	return assign_ticket(ticket_name, technician_user, due_date=due_date, assigned_by=assigned_by, note=note)


@frappe.whitelist()
def wf_technician_ack(ticket_name, message):
	return technician_send_acknowledgement(ticket_name, message)


@frappe.whitelist()
def wf_start_work(ticket_name, message=None):
	return technician_start_work(ticket_name, message=message)


@frappe.whitelist()
def wf_request_customer_input(ticket_name, message):
	return technician_request_customer_input(ticket_name, message)


@frappe.whitelist()
def wf_customer_ack(ticket_name, message):
	return customer_acknowledgement(ticket_name, message)


@frappe.whitelist()
def wf_customer_info_reply(ticket_name, message):
	return customer_informational_reply(ticket_name, message)


@frappe.whitelist()
def wf_customer_provide_info(ticket_name, message):
	return customer_provide_requested_information(ticket_name, message)


@frappe.whitelist()
def wf_customer_followup(ticket_name, message, reopen_from_resolved=0):
	return customer_followup_question(
		ticket_name,
		message,
		reopen_from_resolved=bool(int(reopen_from_resolved or 0)),
	)


@frappe.whitelist()
def wf_resume_work(ticket_name, message=None):
	return technician_resume_after_customer_reply(ticket_name, message=message)


@frappe.whitelist()
def wf_work_update(ticket_name, message):
	return technician_send_work_update(ticket_name, message)


@frappe.whitelist()
def wf_send_resolution(ticket_name, message):
	return technician_send_resolution(ticket_name, message)


@frappe.whitelist()
def wf_customer_confirm(ticket_name, message=None):
	return customer_confirm_resolved(ticket_name, message=message)


@frappe.whitelist()
def wf_manager_close(ticket_name, message=None):
	return manager_close_ticket(ticket_name, message=message)


@frappe.whitelist()
def wf_customer_reopen(ticket_name, message):
	return customer_reopen_issue(ticket_name, message)


@frappe.whitelist()
def wf_internal_note(ticket_name, message):
	return technician_internal_note(ticket_name, message)


@frappe.whitelist()
def wf_cancel(ticket_name, reason=None):
	return cancel_ticket(ticket_name, reason=reason)
