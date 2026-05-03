# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Tickets resolved and Support Tasks completed in a period, attributed to assignees."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, get_first_day, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_set_default_dates(filters)

	from_d = getdate(filters.from_date)
	to_d = getdate(filters.to_date)
	to_exclusive = add_days(to_d, 1)
	employee = filters.get("employee")
	include_tasks = filters.get("include_tasks") not in (0, "0", False, None, "")
	include_tickets = filters.get("include_tickets") not in (0, "0", False, None, "")

	rows: list[dict] = []

	if include_tickets:
		rows.extend(_ticket_rows(from_d, to_exclusive, employee))
	if include_tasks:
		rows.extend(_task_rows(from_d, to_exclusive, employee))

	def _row_key(r):
		co = r.get("completed_on")
		try:
			ts = -get_datetime(co).timestamp() if co else 0.0
		except Exception:
			ts = 0.0
		return ((r.get("employee") or ""), ts)

	rows.sort(key=_row_key)

	columns = [
		{"fieldname": "work_kind", "label": _("Type"), "fieldtype": "Data", "width": 110},
		{
			"fieldname": "document",
			"label": _("Document"),
			"fieldtype": "Dynamic Link",
			"options": "document_type",
			"width": 160,
		},
		{"fieldname": "document_type", "label": _("Document Type"), "fieldtype": "Data", "width": 130},
		{"fieldname": "subject", "label": _("Subject"), "fieldtype": "Data", "width": 220},
		{
			"fieldname": "customer",
			"label": _("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150,
		},
		{
			"fieldname": "employee",
			"label": _("Employee"),
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "completed_on", "label": _("Completed On"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 110},
		{
			"fieldname": "resolution_time_minutes",
			"label": _("Ticket resolution (min)"),
			"fieldtype": "Float",
			"width": 150,
		},
		{"fieldname": "task_type", "label": _("Task type"), "fieldtype": "Data", "width": 130},
	]

	return columns, rows


def _ticket_rows(from_d, to_exclusive, employee: str | None) -> list[dict]:
	params = {"from_d": from_d, "to_ex": to_exclusive}
	user_cond = ""
	if employee:
		user_cond = " AND emp.user = %(employee)s"
		params["employee"] = employee

	# One row per assignee; if no assignee rows, fall back to primary assigned_to.
	sql = f"""
		SELECT
			'Support Ticket' AS work_kind,
			st.name AS document,
			'Support Ticket' AS document_type,
			st.subject AS subject,
			st.customer AS customer,
			emp.user AS employee,
			u.full_name AS employee_name,
			st.resolved_on AS completed_on,
			st.status AS status,
			st.resolution_time_in_minutes AS resolution_time_minutes,
			NULL AS task_type
		FROM `tabSupport Ticket` st
		INNER JOIN `tabSupport Ticket Assignee` emp
			ON emp.parent = st.name AND emp.parenttype = 'Support Ticket'
		LEFT JOIN `tabUser` u ON u.name = emp.user
		WHERE st.docstatus < 2
			AND st.resolved_on IS NOT NULL
			AND st.resolved_on >= %(from_d)s
			AND st.resolved_on < %(to_ex)s
			{user_cond}

		UNION ALL

		SELECT
			'Support Ticket' AS work_kind,
			st.name AS document,
			'Support Ticket' AS document_type,
			st.subject AS subject,
			st.customer AS customer,
			st.assigned_to AS employee,
			u.full_name AS employee_name,
			st.resolved_on AS completed_on,
			st.status AS status,
			st.resolution_time_in_minutes AS resolution_time_minutes,
			NULL AS task_type
		FROM `tabSupport Ticket` st
		LEFT JOIN `tabUser` u ON u.name = st.assigned_to
		WHERE st.docstatus < 2
			AND st.resolved_on IS NOT NULL
			AND st.resolved_on >= %(from_d)s
			AND st.resolved_on < %(to_ex)s
			AND IFNULL(st.assigned_to, '') != ''
			AND NOT EXISTS (
				SELECT 1 FROM `tabSupport Ticket Assignee` ta
				WHERE ta.parent = st.name AND ta.parenttype = 'Support Ticket'
			)
			{"AND st.assigned_to = %(employee)s" if employee else ""}
	"""

	return frappe.db.sql(sql, params, as_dict=True)


def _task_rows(from_d, to_exclusive, employee: str | None) -> list[dict]:
	params = {"from_d": from_d, "to_ex": to_exclusive}
	user_cond = ""
	if employee:
		user_cond = " AND emp.user = %(employee)s"
		params["employee"] = employee

	sql = f"""
		SELECT
			'Support Task' AS work_kind,
			t.name AS document,
			'Support Task' AS document_type,
			t.subject AS subject,
			t.customer AS customer,
			emp.user AS employee,
			u.full_name AS employee_name,
			t.actual_end_date AS completed_on,
			t.status AS status,
			NULL AS resolution_time_minutes,
			t.task_type AS task_type
		FROM `tabSupport Task` t
		INNER JOIN `tabSupport Task Assignee` emp
			ON emp.parent = t.name AND emp.parenttype = 'Support Task'
		LEFT JOIN `tabUser` u ON u.name = emp.user
		WHERE t.docstatus < 2
			AND t.status = 'Completed'
			AND IFNULL(t.actual_end_date, t.modified) >= %(from_d)s
			AND IFNULL(t.actual_end_date, t.modified) < %(to_ex)s
			{user_cond}

		UNION ALL

		SELECT
			'Support Task' AS work_kind,
			t.name AS document,
			'Support Task' AS document_type,
			t.subject AS subject,
			t.customer AS customer,
			t.assigned_to_user AS employee,
			u.full_name AS employee_name,
			t.actual_end_date AS completed_on,
			t.status AS status,
			NULL AS resolution_time_minutes,
			t.task_type AS task_type
		FROM `tabSupport Task` t
		LEFT JOIN `tabUser` u ON u.name = t.assigned_to_user
		WHERE t.docstatus < 2
			AND t.status = 'Completed'
			AND IFNULL(t.actual_end_date, t.modified) >= %(from_d)s
			AND IFNULL(t.actual_end_date, t.modified) < %(to_ex)s
			AND IFNULL(t.assigned_to_user, '') != ''
			AND NOT EXISTS (
				SELECT 1 FROM `tabSupport Task Assignee` ta
				WHERE ta.parent = t.name AND ta.parenttype = 'Support Task'
			)
			{"AND t.assigned_to_user = %(employee)s" if employee else ""}
	"""

	return frappe.db.sql(sql, params, as_dict=True)


def _set_default_dates(filters):
	if not filters.get("from_date"):
		filters.from_date = get_first_day(today())
	if not filters.get("to_date"):
		filters.to_date = today()
