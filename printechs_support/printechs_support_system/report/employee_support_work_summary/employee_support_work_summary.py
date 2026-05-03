# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Per-employee totals: resolved tickets (with SLA minutes split across assignees), completed tasks."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_set_default_dates(filters)

	from_d = getdate(filters.from_date)
	to_d = getdate(filters.to_date)
	to_exclusive = add_days(to_d, 1)
	employee = filters.get("employee")
	include_tasks = filters.get("include_tasks") not in (0, "0", False, None, "")
	include_tickets = filters.get("include_tickets") not in (0, "0", False, None, "")

	agg: dict[str, dict] = defaultdict(
		lambda: {
			"employee": "",
			"employee_name": "",
			"tickets_resolved": 0,
			"ticket_resolution_minutes": 0.0,
			"ticket_resolution_hours": 0.0,
			"tasks_completed": 0,
		}
	)

	if include_tickets:
		for row in _ticket_summary_assignee_path(from_d, to_exclusive, employee):
			_merge_ticket_row(agg, row)
		for row in _ticket_summary_primary_only_path(from_d, to_exclusive, employee):
			_merge_ticket_row(agg, row)

	if include_tasks:
		for row in _task_summary_assignee_path(from_d, to_exclusive, employee):
			_merge_task_row(agg, row)
		for row in _task_summary_primary_only_path(from_d, to_exclusive, employee):
			_merge_task_row(agg, row)

	rows: list[dict] = []
	for user_id, data in agg.items():
		if not user_id:
			continue
		data["ticket_resolution_hours"] = flt((data["ticket_resolution_minutes"] or 0) / 60.0, 2)
		rows.append(data)

	rows.sort(key=lambda r: (r.get("employee_name") or r.get("employee") or ""))

	columns = [
		{
			"fieldname": "employee",
			"label": _("Employee"),
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 180},
		{
			"fieldname": "tickets_resolved",
			"label": _("Tickets resolved"),
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"fieldname": "ticket_resolution_minutes",
			"label": _("Ticket resolution (min, split)"),
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"fieldname": "ticket_resolution_hours",
			"label": _("Ticket resolution (hrs, split)"),
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"fieldname": "tasks_completed",
			"label": _("Tasks completed"),
			"fieldtype": "Int",
			"width": 130,
		},
	]

	return columns, rows


def _merge_ticket_row(agg: dict, row: dict) -> None:
	uid = row.get("employee")
	if not uid:
		return
	a = agg[uid]
	a["employee"] = uid
	a["employee_name"] = row.get("employee_name") or a["employee_name"]
	a["tickets_resolved"] += int(row.get("tickets_resolved") or 0)
	a["ticket_resolution_minutes"] = flt(
		flt(a["ticket_resolution_minutes"]) + flt(row.get("ticket_resolution_minutes")), 2
	)


def _merge_task_row(agg: dict, row: dict) -> None:
	uid = row.get("employee")
	if not uid:
		return
	a = agg[uid]
	a["employee"] = uid
	a["employee_name"] = row.get("employee_name") or a["employee_name"]
	a["tasks_completed"] += int(row.get("tasks_completed") or 0)


def _ticket_summary_assignee_path(from_d, to_exclusive, employee: str | None) -> list[dict]:
	"""Fair share: each ticket's resolution minutes divided by number of assignees."""
	params = {"from_d": from_d, "to_ex": to_exclusive}
	user_cond = ""
	if employee:
		user_cond = " AND emp.user = %(employee)s"
		params["employee"] = employee

	sql = f"""
		SELECT
			emp.user AS employee,
			MAX(u.full_name) AS employee_name,
			COUNT(DISTINCT st.name) AS tickets_resolved,
			SUM(st.resolution_time_in_minutes / NULLIF(ac.assignee_count, 0)) AS ticket_resolution_minutes
		FROM `tabSupport Ticket` st
		INNER JOIN `tabSupport Ticket Assignee` emp
			ON emp.parent = st.name AND emp.parenttype = 'Support Ticket'
		LEFT JOIN `tabUser` u ON u.name = emp.user
		INNER JOIN (
			SELECT parent, COUNT(*) AS assignee_count
			FROM `tabSupport Ticket Assignee`
			WHERE parenttype = 'Support Ticket'
			GROUP BY parent
		) ac ON ac.parent = st.name
		WHERE st.docstatus < 2
			AND st.resolved_on IS NOT NULL
			AND st.resolved_on >= %(from_d)s
			AND st.resolved_on < %(to_ex)s
			{user_cond}
		GROUP BY emp.user
	"""
	return frappe.db.sql(sql, params, as_dict=True)


def _ticket_summary_primary_only_path(from_d, to_exclusive, employee: str | None) -> list[dict]:
	params = {"from_d": from_d, "to_ex": to_exclusive}
	user_cond = ""
	if employee:
		user_cond = " AND st.assigned_to = %(employee)s"
		params["employee"] = employee

	sql = f"""
		SELECT
			st.assigned_to AS employee,
			MAX(u.full_name) AS employee_name,
			COUNT(*) AS tickets_resolved,
			SUM(st.resolution_time_in_minutes) AS ticket_resolution_minutes
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
			{user_cond}
		GROUP BY st.assigned_to
	"""
	return frappe.db.sql(sql, params, as_dict=True)


def _task_summary_assignee_path(from_d, to_exclusive, employee: str | None) -> list[dict]:
	params = {"from_d": from_d, "to_ex": to_exclusive}
	user_cond = ""
	if employee:
		user_cond = " AND emp.user = %(employee)s"
		params["employee"] = employee

	sql = f"""
		SELECT
			emp.user AS employee,
			MAX(u.full_name) AS employee_name,
			COUNT(DISTINCT t.name) AS tasks_completed
		FROM `tabSupport Task` t
		INNER JOIN `tabSupport Task Assignee` emp
			ON emp.parent = t.name AND emp.parenttype = 'Support Task'
		LEFT JOIN `tabUser` u ON u.name = emp.user
		WHERE t.docstatus < 2
			AND t.status = 'Completed'
			AND IFNULL(t.actual_end_date, t.modified) >= %(from_d)s
			AND IFNULL(t.actual_end_date, t.modified) < %(to_ex)s
			{user_cond}
		GROUP BY emp.user
	"""
	return frappe.db.sql(sql, params, as_dict=True)


def _task_summary_primary_only_path(from_d, to_exclusive, employee: str | None) -> list[dict]:
	params = {"from_d": from_d, "to_ex": to_exclusive}
	user_cond = ""
	if employee:
		user_cond = " AND t.assigned_to_user = %(employee)s"
		params["employee"] = employee

	sql = f"""
		SELECT
			t.assigned_to_user AS employee,
			MAX(u.full_name) AS employee_name,
			COUNT(*) AS tasks_completed
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
			{user_cond}
		GROUP BY t.assigned_to_user
	"""
	return frappe.db.sql(sql, params, as_dict=True)


def _set_default_dates(filters):
	if not filters.get("from_date"):
		filters.from_date = get_first_day(today())
	if not filters.get("to_date"):
		filters.to_date = today()
