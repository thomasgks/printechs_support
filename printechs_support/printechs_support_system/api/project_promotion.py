# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Promote ERPNext Project Tasks (planning) into Support Ticket + Support Task after customer confirmation."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime

from printechs_support.project_plan_flags import ENABLE_PROJECT_PLAN_INTEGRATION


def _task_to_datetimes(task) -> tuple:
	"""Return (planned_start, planned_end, due) from Task schedule fields."""
	ps = get_datetime(task.exp_start_date) if task.exp_start_date else None
	pe = get_datetime(task.exp_end_date) if task.exp_end_date else None
	due = pe or ps
	return ps, pe, due


def _existing_support_for_project_task(project_task_name: str) -> str | None:
	return frappe.db.get_value("Support Task", {"source_project_task": project_task_name}, "name")


def _resolve_predecessor(
	task,
	created_map: dict[str, str],
) -> str | None:
	"""Map ERPNext parent_task to Support Task name (in-batch or already promoted)."""
	if not task.parent_task:
		return None
	if task.parent_task in created_map:
		return created_map[task.parent_task]
	existing = _existing_support_for_project_task(task.parent_task)
	return existing


@frappe.whitelist()
def get_tasks_for_project_promotion(project: str):
	"""Leaf Project Tasks for the promote dialog, with promotion status."""
	if not ENABLE_PROJECT_PLAN_INTEGRATION:
		frappe.throw(_("Project plan integration is disabled."), frappe.ValidationError)

	project = (project or "").strip()
	if not project or not frappe.db.exists("Project", project):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	if not frappe.has_permission("Project", "read", project):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	rows = frappe.get_all(
		"Task",
		filters={"project": project, "is_group": 0},
		fields=["name", "subject", "parent_task", "lft", "status"],
		order_by="lft asc, name asc",
	)
	out = []
	for r in rows:
		out.append(
			{
				**r,
				"already_promoted": bool(_existing_support_for_project_task(r.name)),
			}
		)
	return out


@frappe.whitelist()
def promote_project_tasks_to_support(
	project: str,
	task_names,
	support_ticket: str | None = None,
	ticket_subject: str | None = None,
	new_ticket_status: str = "Open",
):
	"""Create a Support Ticket (unless ``support_ticket`` is passed) and Support Tasks from selected ERPNext Tasks.

	- Use **Project → Task** for internal planning; when the customer confirms, run this.

	:param project: Project name
	:param task_names: JSON list or list of Task names (leaf tasks)
	:param support_ticket: Optional existing Support Ticket to attach tasks to (same project + customer)
	:param ticket_subject: Subject for a new Support Ticket (required if creating new)
	:param new_ticket_status: ``Open``, ``Assigned``, or ``In Progress`` for new ticket (legacy ``Draft`` / ``Acknowledged`` are mapped).
	"""
	if not ENABLE_PROJECT_PLAN_INTEGRATION:
		frappe.throw(_("Project plan integration is disabled."), frappe.ValidationError)

	project = (project or "").strip()
	if not project or not frappe.db.exists("Project", project):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	if not frappe.has_permission("Project", "write", project):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not frappe.has_permission("Support Task", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if isinstance(task_names, str):
		import json

		task_names = json.loads(task_names)

	if not task_names or not isinstance(task_names, (list, tuple)):
		frappe.throw(_("Select at least one Project Task."))

	task_names = [str(t).strip() for t in task_names if str(t).strip()]
	if not task_names:
		frappe.throw(_("Select at least one Project Task."))

	project_doc = frappe.get_doc("Project", project)
	if not project_doc.customer:
		frappe.throw(_("Set a Customer on the Project before promoting to Support."))

	if len(task_names) > 200:
		frappe.throw(_("Too many tasks in one run (max 200)."))

	new_ticket_status = (new_ticket_status or "Open").strip()
	legacy_map = {"Draft": "Open", "Acknowledged": "Assigned"}
	new_ticket_status = legacy_map.get(new_ticket_status, new_ticket_status)
	if new_ticket_status not in ("Open", "Assigned", "In Progress"):
		frappe.throw(_("Ticket status must be Open, Assigned, or In Progress."))

	for tn in task_names:
		t = frappe.db.get_value(
			"Task",
			tn,
			["name", "project", "is_group"],
			as_dict=True,
		)
		if not t or t.project != project:
			frappe.throw(_("Task {0} is not part of this project.").format(tn))
		if t.is_group:
			frappe.throw(_("Task {0} is a group — select leaf tasks only.").format(tn))

	# Sort selected tasks by tree order so parent links resolve first
	ordered = frappe.get_all(
		"Task",
		filters={"name": ["in", task_names]},
		fields=["name", "parent_task", "lft"],
		order_by="lft asc, name asc",
	)
	ordered_names = [r.name for r in ordered]

	ticket_name = (support_ticket or "").strip() or None
	if ticket_name:
		if not frappe.has_permission("Support Ticket", "write", ticket_name):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if not frappe.db.exists("Support Ticket", ticket_name):
			frappe.throw(_("Support Ticket not found."))
		st = frappe.db.get_value(
			"Support Ticket",
			ticket_name,
			["customer", "project", "name"],
			as_dict=True,
		)
		if st.customer != project_doc.customer:
			frappe.throw(_("Support Ticket customer must match the Project customer."))
		if st.project and st.project != project:
			frappe.throw(_("Support Ticket project must match this Project (or be empty)."))
	else:
		if not frappe.has_permission("Support Ticket", "create"):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		subj = (ticket_subject or "").strip() or f"{project_doc.project_name} — Support"
		ticket = frappe.get_doc(
			{
				"doctype": "Support Ticket",
				"subject": subj,
				"customer": project_doc.customer,
				"project": project_doc.name,
				"status": new_ticket_status,
			}
		)
		ticket.insert()
		ticket_name = ticket.name

	created: list[str] = []
	skipped: list[dict] = []

	created_map: dict[str, str] = {}

	for erp_name in ordered_names:
		if _existing_support_for_project_task(erp_name):
			skipped.append({"task": erp_name, "reason": "already_promoted"})
			continue

		task = frappe.get_doc("Task", erp_name)
		ps, pe, due = _task_to_datetimes(task)
		pred = _resolve_predecessor(task, created_map)

		st = frappe.get_doc(
			{
				"doctype": "Support Task",
				"support_ticket": ticket_name,
				"project": project_doc.name,
				"source_project_task": task.name,
				"subject": task.subject or _("Untitled task"),
				"description": task.description or "",
				"task_type": "Implementation Step",
				"status": "Open",
				"planned_start_date": ps,
				"planned_end_date": pe,
				"due_date": due,
				"predecessor_task": pred,
			}
		)
		st.insert()
		created_map[task.name] = st.name
		created.append(st.name)

	return {
		"support_ticket": ticket_name,
		"created_tasks": created,
		"skipped": skipped,
	}
