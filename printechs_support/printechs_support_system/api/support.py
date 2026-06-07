# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from datetime import time

import frappe
from frappe import _
from frappe.model.workflow import get_workflow, get_workflow_name
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime


def get_initial_support_ticket_status() -> str:
	"""Initial ``status`` for new Support Tickets.

	If a legacy Frappe **Workflow** still exists, its first state may be *Draft* or other labels
	that are not valid options on the Support Ticket ``status`` field (smart workflow vocabulary).
	In that case we map legacy states and otherwise fall back to ``Open``.
	"""
	if not get_workflow_name("Support Ticket"):
		return "Open"
	wf = get_workflow("Support Ticket")
	if not wf.states:
		return "Open"
	state = (wf.states[0].state or "").strip()
	# Same mapping as patches.v1_0.migrate_support_ticket_smart_workflow (keep in sync).
	legacy = {
		"Draft": "Open",
		"Acknowledged": "Assigned",
		"Waiting for Internal Team": "Waiting for Technician",
		"Waiting for Approval": "Open",
	}
	state = legacy.get(state, state)
	from printechs_support.printechs_support_system.api.ticket_workflow import WF_STATUSES

	if state not in WF_STATUSES:
		return "Open"
	return state


def get_active_support_agreements(
	customer: str,
	division: str | None = None,
	project: str | None = None,
	software_product: str | None = None,
) -> list[dict]:
	"""Return candidate Support Agreement rows for auto-linking (Active + in validity window)."""
	if not customer:
		return []

	today = getdate()
	filters: dict = {"customer": customer, "status": "Active"}
	if division:
		filters["division"] = division

	rows = frappe.get_all(
		"Support Agreement",
		filters=filters,
		fields=["name", "valid_from", "valid_to", "grace_period_days", "project", "software_product", "modified"],
		order_by="modified desc",
	)

	out = []
	for row in rows:
		vf = row.valid_from and getdate(row.valid_from)
		vt = row.valid_to and getdate(row.valid_to)
		grace = int(row.grace_period_days or 0)
		if vf and today < vf:
			continue
		if vt:
			vt_grace = add_to_date(vt, days=grace)
			if today > getdate(vt_grace):
				continue
		out.append(row)

	if project or software_product:
		scored = []
		for row in out:
			ag = frappe.get_doc("Support Agreement", row.name)
			score = 0
			if project and ag.project == project:
				score += 2
			if software_product and ag.software_product == software_product:
				score += 2
			scored.append((score, row))
		scored.sort(key=lambda x: -x[0])
		return [r for _s, r in scored]
	return out


def auto_link_support_agreement(doc) -> None:
	"""Pick best Support Agreement for the ticket when missing."""
	if getattr(doc, "work_scope", None) == "Internal":
		doc.support_agreement = None
		return
	if getattr(doc, "support_agreement", None):
		return
	customer = getattr(doc, "customer", None)
	if not customer:
		return

	division = getattr(doc, "division", None) or "Software"
	project = getattr(doc, "project", None)
	product = getattr(doc, "software_product", None)

	candidates = get_active_support_agreements(
		customer,
		division=division,
		project=project,
		software_product=product,
	)

	if not candidates:
		candidates = get_active_support_agreements(
			customer,
			division=None,
			project=project,
			software_product=product,
		)

	if len(candidates) == 1:
		doc.support_agreement = candidates[0].name
	elif len(candidates) > 1:
		best = None
		best_score = -1
		for row in candidates:
			ag = frappe.get_doc("Support Agreement", row.name)
			score = 0
			if project and ag.project == project:
				score += 3
			if product and ag.software_product == product:
				score += 3
			if division and ag.division == division:
				score += 1
			if score > best_score:
				best_score = score
				best = ag.name
		if best:
			doc.support_agreement = best


def _get_coverage_override(agreement, service_category: str | None) -> tuple[float | None, float | None]:
	if not service_category or not agreement.coverage_detail:
		return (None, None)
	sc = (service_category or "").strip()
	for row in agreement.coverage_detail:
		if not row.is_covered:
			continue
		if row.coverage_type:
			title = frappe.db.get_value("Coverage Type", row.coverage_type, "title")
			if title and title.strip() == sc:
				return (row.response_sla_hours, row.resolution_sla_hours)
		elif row.service_category and row.service_category.strip() == sc:
			return (row.response_sla_hours, row.resolution_sla_hours)
	return (None, None)


def _get_sla_template_hours(ticket_type: str | None, priority: str | None) -> tuple[float | None, float | None]:
	if not ticket_type or not priority:
		return (None, None)
	names = frappe.get_all(
		"Support SLA Template",
		filters={"ticket_type": ticket_type, "priority": priority},
		pluck="name",
		limit=1,
	)
	if not names:
		return (None, None)
	row = frappe.get_doc("Support SLA Template", names[0])
	return (row.first_response_hours, row.resolution_hours)


def get_sla_hours_for_ticket(doc) -> tuple[float, float]:
	"""SLA priority: coverage detail → agreement → SLA template → default."""
	resp: float | None = None
	reso: float | None = None

	service_category = getattr(doc, "service_category", None)
	ticket_type = getattr(doc, "ticket_type", None)
	priority = getattr(doc, "priority", None) or "Medium"

	if doc.support_agreement:
		ag = frappe.get_doc("Support Agreement", doc.support_agreement)
		resp, reso = _get_coverage_override(ag, service_category)
		if resp is None:
			resp = flt(ag.response_sla_hours)
		if reso is None:
			reso = flt(ag.resolution_sla_hours)

	if (resp is None or reso is None or resp <= 0 or reso <= 0) and ticket_type:
		tr, tz = _get_sla_template_hours(ticket_type, priority)
		if resp is None or resp <= 0:
			resp = tr
		if reso is None or reso <= 0:
			reso = tz

	if resp is None or resp <= 0:
		resp = 8.0
	if reso is None or reso <= 0:
		reso = 48.0

	return (float(resp), float(reso))


def get_sla_working_hours_policy(doc) -> dict:
	"""When agreement has Working Hours Only, return work window + holiday list for SLA deadlines."""
	from printechs_support.printechs_support_system.api.sla_business_hours import parse_time_value
	from printechs_support.printechs_support_system.doctype.printechs_support_settings.printechs_support_settings import (
		get_settings,
	)

	defaults = {
		"use_working_hours": False,
		"work_start": time(9, 0),
		"work_end": time(18, 0),
		"holiday_list": None,
	}
	if not getattr(doc, "support_agreement", None):
		return defaults

	ag = frappe.get_doc("Support Agreement", doc.support_agreement)
	if not cint(ag.working_hours_only):
		return defaults

	settings = get_settings()
	ws = parse_time_value(ag.work_start_time) or parse_time_value(settings.default_work_start) or time(9, 0)
	we = parse_time_value(ag.work_end_time) or parse_time_value(settings.default_work_end) or time(18, 0)
	holist = ag.sla_holiday_list or settings.default_holiday_list

	return {
		"use_working_hours": True,
		"work_start": ws,
		"work_end": we,
		"holiday_list": holist,
	}


def apply_sla_to_ticket(doc) -> None:
	"""Set SLA due datetimes from opening_date + SLA hours (calendar or business hours)."""
	base = getattr(doc, "opening_date", None) or now_datetime()
	if isinstance(base, str):
		base = get_datetime(base)
	doc.opening_date = base

	first_h, res_h = get_sla_hours_for_ticket(doc)
	policy = get_sla_working_hours_policy(doc)

	if not getattr(doc, "support_agreement", None):
		doc.first_response_due = add_to_date(base, hours=first_h, as_datetime=True)
		doc.resolution_due = add_to_date(base, hours=res_h, as_datetime=True)
		return

	if policy["use_working_hours"]:
		from printechs_support.printechs_support_system.api.sla_business_hours import add_working_hours, get_holiday_dates

		hol = get_holiday_dates(policy["holiday_list"])
		doc.first_response_due = add_working_hours(
			base, first_h, policy["work_start"], policy["work_end"], hol
		)
		doc.resolution_due = add_working_hours(
			base, res_h, policy["work_start"], policy["work_end"], hol
		)
	else:
		doc.first_response_due = add_to_date(base, hours=first_h, as_datetime=True)
		doc.resolution_due = add_to_date(base, hours=res_h, as_datetime=True)


def resolve_customer_from_email(email: str | None) -> str | None:
	"""Resolve Customer from Contact primary / child email linked to Customer."""
	if not email:
		return None
	email = email.strip().lower()
	if not email:
		return None

	contact_rows = frappe.db.sql(
		"""
		SELECT name FROM `tabContact` WHERE LOWER(TRIM(IFNULL(email_id, ''))) = %s
		UNION
		SELECT parent FROM `tabContact Email` WHERE LOWER(TRIM(IFNULL(email_id, ''))) = %s
		""",
		(email, email),
	)
	for (contact_name,) in contact_rows:
		cust = frappe.db.get_value(
			"Dynamic Link",
			{
				"parent": contact_name,
				"parenttype": "Contact",
				"link_doctype": "Customer",
			},
			"link_name",
		)
		if cust:
			return cust
	return None


def inherit_from_agreement(doc) -> None:
	if not doc.support_agreement:
		return
	ag = frappe.get_doc("Support Agreement", doc.support_agreement)
	if not doc.division:
		doc.division = ag.division
	if not doc.priority and ag.default_priority:
		doc.priority = ag.default_priority


def apply_ticket_metrics(doc) -> None:
	"""Overdue flag and elapsed minutes."""
	now = now_datetime()
	opening = getattr(doc, "opening_date", None)
	first_on = getattr(doc, "first_response_on", None)
	res_on = getattr(doc, "resolved_on", None)

	if opening and first_on:
		doc.response_time_in_minutes = (get_datetime(first_on) - get_datetime(opening)).total_seconds() / 60.0

	if opening and res_on:
		doc.resolution_time_in_minutes = (get_datetime(res_on) - get_datetime(opening)).total_seconds() / 60.0

	closed_statuses = ("Resolved", "Closed", "Cancelled")
	if doc.status not in closed_statuses and doc.resolution_due:
		if now > get_datetime(doc.resolution_due):
			doc.is_overdue = 1
		else:
			doc.is_overdue = 0
	else:
		doc.is_overdue = 0


def mark_first_response(ticket_name: str) -> None:
	doc = frappe.get_doc("Support Ticket", ticket_name)
	if doc.first_response_on:
		return
	doc.first_response_on = now_datetime()
	doc.save()


@frappe.whitelist()
def mark_first_response_api(ticket_name: str) -> None:
	from printechs_support.permissions import user_sees_all_support_records

	if not user_sees_all_support_records(frappe.session.user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	mark_first_response(ticket_name)


def resolve_ticket(ticket_name: str, resolution_summary: str | None = None) -> None:
	doc = frappe.get_doc("Support Ticket", ticket_name)
	doc.status = "Resolved"
	doc.resolved_on = now_datetime()
	doc.action_required_from = "Customer"
	doc.current_owner_type = "Customer"
	if resolution_summary:
		doc.resolution_summary = resolution_summary
	doc.save()


@frappe.whitelist()
def resolve_ticket_api(ticket_name: str, resolution_summary: str | None = None) -> None:
	from printechs_support.permissions import user_sees_all_support_records

	if not user_sees_all_support_records(frappe.session.user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	resolve_ticket(ticket_name, resolution_summary=resolution_summary)


def reopen_ticket(ticket_name: str) -> None:
	doc = frappe.get_doc("Support Ticket", ticket_name)
	doc.status = "Reopened"
	doc.action_required_from = "Technician"
	doc.current_owner_type = "Technician"
	doc.is_reopened = 1
	doc.reopened_count = int(doc.reopened_count or 0) + 1
	doc.save()


@frappe.whitelist()
def reopen_ticket_api(ticket_name: str) -> None:
	from printechs_support.permissions import user_sees_all_support_records

	if not user_sees_all_support_records(frappe.session.user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	reopen_ticket(ticket_name)


def update_overdue_flags() -> None:
	"""Scheduled: refresh overdue on open tickets."""
	for name in frappe.get_all(
		"Support Ticket",
		filters={"status": ["not in", ["Resolved", "Closed", "Cancelled"]]},
		pluck="name",
	):
		doc = frappe.get_doc("Support Ticket", name)
		apply_ticket_metrics(doc)
		doc.db_set("is_overdue", doc.is_overdue, update_modified=False)


def send_daily_task_reminders() -> None:
	"""Email assignees for Support Tasks whose reminder date is today."""
	from html import escape as html_escape

	from frappe.utils import getdate, today

	today_date = getdate(today())
	tasks = frappe.db.sql(
		"""
		SELECT name, subject, support_ticket, assigned_email, reminder_datetime
		FROM `tabSupport Task`
		WHERE send_email_reminder = 1
			AND reminder_datetime IS NOT NULL
			AND DATE(reminder_datetime) = %(d)s
			AND IFNULL(assigned_email, '') != ''
			AND status NOT IN ('Completed', 'Cancelled')
		""",
		{"d": today_date},
		as_dict=True,
	)

	for row in tasks:
		ticket = row.support_ticket or ""
		subj = row.subject or row.name
		try:
			desc_html = ""
			if ticket and frappe.db.exists("Support Ticket", ticket):
				st_doc = frappe.get_doc("Support Ticket", ticket)
				desc_html = st_doc.get_acknowledgement_description_block_html(max_chars=2500)
			message = frappe._(
				"<p>This is a reminder for support task <b>{0}</b> on ticket <b>{1}</b>.</p>"
			).format(html_escape(str(subj)), html_escape(str(ticket) or "—"))
			message += desc_html
			frappe.sendmail(
				recipients=[row.assigned_email],
				subject=frappe._("Reminder: {0} ({1})").format(subj, ticket),
				message=message,
				reference_doctype="Support Task",
				reference_name=row.name,
				delayed=False,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "send_daily_task_reminders")


def build_monthly_support_summary() -> None:
	pass


def build_delay_analysis_snapshot() -> None:
	pass
