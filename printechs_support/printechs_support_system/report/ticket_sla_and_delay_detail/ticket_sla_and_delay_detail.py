# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Per-customer ticket list with SLA timestamps, duration, and delay accountability."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_set_default_dates(filters)

	from_d = getdate(filters.from_date)
	to_d = getdate(filters.to_date)
	to_exclusive = add_days(to_d, 1)
	basis = filters.get("period_based_on") or "Resolved Date"

	conditions = ["st.docstatus < 2"]
	params: dict = {"from_d": from_d, "to_ex": to_exclusive}

	if filters.get("customer"):
		conditions.append("st.customer = %(customer)s")
		params["customer"] = filters.customer

	if filters.get("status"):
		conditions.append("st.status = %(status)s")
		params["status"] = filters.status

	if filters.get("work_scope"):
		conditions.append("st.work_scope = %(work_scope)s")
		params["work_scope"] = filters.work_scope

	if basis == "Opening Date":
		conditions.append("st.opening_date >= %(from_d)s AND st.opening_date < %(to_ex)s")
	elif basis == "Closed Date":
		conditions.append(
			"st.closed_on IS NOT NULL AND st.closed_on >= %(from_d)s AND st.closed_on < %(to_ex)s"
		)
	else:
		conditions.append(
			"st.resolved_on IS NOT NULL AND st.resolved_on >= %(from_d)s AND st.resolved_on < %(to_ex)s"
		)

	where_sql = " AND ".join(conditions)

	query = f"""
		SELECT
			st.name AS ticket,
			st.subject AS subject,
			st.customer AS customer,
			st.customer_name AS customer_name,
			st.work_scope AS work_scope,
			st.status AS status,
			st.priority AS priority,
			st.ticket_type AS ticket_type,
			st.opening_date AS opening_date,
			st.due_date AS due_date,
			st.first_response_due AS first_response_due,
			st.resolution_due AS resolution_due,
			st.first_response_on AS first_response_on,
			st.resolved_on AS resolved_on,
			st.closed_on AS closed_on,
			st.response_time_in_minutes AS response_time_minutes,
			st.resolution_time_in_minutes AS resolution_time_minutes,
			ROUND(IFNULL(st.response_time_in_minutes, 0) / 60, 2) AS response_time_hours,
			ROUND(IFNULL(st.resolution_time_in_minutes, 0) / 60, 2) AS resolution_time_hours,
			ROUND(IFNULL(st.resolution_time_in_minutes, 0) / 1440, 4) AS resolution_time_days,
			st.is_overdue AS is_overdue,
			st.delay_owner AS delay_owner,
			IFNULL(dr.reason_name, st.delay_reason) AS delay_reason,
			st.delay_remarks AS delay_remarks,
			st.waiting_for_side AS waiting_for_side,
			st.waiting_since AS waiting_since,
			st.total_waiting_time_hours AS total_waiting_time_hours,
			st.assigned_to AS assigned_to,
			st.customer_resolution_deadline AS customer_resolution_deadline
		FROM `tabSupport Ticket` st
		LEFT JOIN `tabDelay Reason` dr ON dr.name = st.delay_reason
		WHERE {where_sql}
		ORDER BY st.customer ASC, st.resolved_on DESC, st.opening_date DESC
	"""

	rows = frappe.db.sql(query, params, as_dict=True)

	columns = [
		{
			"fieldname": "ticket",
			"label": _("Ticket"),
			"fieldtype": "Link",
			"options": "Support Ticket",
			"width": 160,
		},
		{"fieldname": "subject", "label": _("Subject"), "fieldtype": "Data", "width": 220},
		{
			"fieldname": "customer",
			"label": _("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "work_scope", "label": _("Work scope"), "fieldtype": "Data", "width": 90},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "priority", "label": _("Priority"), "fieldtype": "Data", "width": 90},
		{
			"fieldname": "ticket_type",
			"label": _("Ticket Type"),
			"fieldtype": "Link",
			"options": "Support Ticket Type",
			"width": 140,
		},
		{"fieldname": "opening_date", "label": _("Opening Date"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "due_date", "label": _("Due Date"), "fieldtype": "Datetime", "width": 150},
		{
			"fieldname": "first_response_due",
			"label": _("First Response Due"),
			"fieldtype": "Datetime",
			"width": 150,
		},
		{
			"fieldname": "resolution_due",
			"label": _("Resolution Due"),
			"fieldtype": "Datetime",
			"width": 150,
		},
		{
			"fieldname": "first_response_on",
			"label": _("First Response On"),
			"fieldtype": "Datetime",
			"width": 150,
		},
		{"fieldname": "resolved_on", "label": _("Resolved On"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "closed_on", "label": _("Closed On"), "fieldtype": "Datetime", "width": 150},
		{
			"fieldname": "response_time_minutes",
			"label": _("Response Time (min)"),
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"fieldname": "resolution_time_minutes",
			"label": _("Resolution Time (min)"),
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"fieldname": "response_time_hours",
			"label": _("Response Time (hrs)"),
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"fieldname": "resolution_time_hours",
			"label": _("Resolution Time (hrs)"),
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"fieldname": "resolution_time_days",
			"label": _("Resolution Time (days)"),
			"fieldtype": "Float",
			"width": 140,
		},
		{"fieldname": "is_overdue", "label": _("Overdue flag"), "fieldtype": "Check", "width": 100},
		{"fieldname": "delay_owner", "label": _("Delay Owner"), "fieldtype": "Data", "width": 120},
		{"fieldname": "delay_reason", "label": _("Delay Reason"), "fieldtype": "Data", "width": 180},
		{"fieldname": "delay_remarks", "label": _("Delay Remarks"), "fieldtype": "Small Text", "width": 220},
		{
			"fieldname": "waiting_for_side",
			"label": _("Waiting For Side"),
			"fieldtype": "Data",
			"width": 130,
		},
		{"fieldname": "waiting_since", "label": _("Waiting Since"), "fieldtype": "Datetime", "width": 150},
		{
			"fieldname": "total_waiting_time_hours",
			"label": _("Total Waiting (hrs)"),
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"fieldname": "assigned_to",
			"label": _("Assigned To"),
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{
			"fieldname": "customer_resolution_deadline",
			"label": _("Customer Resolution Deadline"),
			"fieldtype": "Datetime",
			"width": 170,
		},
	]

	return columns, rows


def _set_default_dates(filters):
	if not filters.get("from_date"):
		filters.from_date = get_first_day(today())
	if not filters.get("to_date"):
		filters.to_date = today()
