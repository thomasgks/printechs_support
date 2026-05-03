# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Sync Support Task → ERPNext Project Task (plan) when ``source_project_task`` is set."""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate, today

from printechs_support.project_plan_flags import ENABLE_PROJECT_PLAN_INTEGRATION


# Support Task status → ERPNext Task.status
# ERPNext options: Open | Working | Pending Review | Overdue | Completed | Cancelled | Template
#
# Mapping intent (project plan stays readable on the Project / Gantt):
# - Open              → not started / backlog on the plan
# - In Progress       → someone is actively executing (hands-on)
# - Waiting for Customer → blocked on the customer / external input (use Pending Review = “waiting”)
# - Waiting for Printechs → next step is on Printechs (keep in Working so it does not look like “not started”)
# - Delayed           → Overdue on the plan
# - Completed / Cancelled → terminal states
#
# Note: In Progress and Waiting for Printechs both map to Working; use “Project plan progress %” on the
# Support Task to fine-tune % on the ERPNext Task when you need more nuance.
SUPPORT_TO_TASK_STATUS = {
	"Open": "Open",
	"In Progress": "Working",
	"Waiting for Customer": "Pending Review",
	"Waiting for Printechs": "Working",
	"Completed": "Completed",
	"Cancelled": "Cancelled",
	"Delayed": "Overdue",
}


def _pct_eq(a, b) -> bool:
	if a is None and b is None:
		return True
	if a is None or b is None:
		return False
	try:
		return abs(float(a) - float(b)) < 0.001
	except (TypeError, ValueError):
		return False


def _should_sync_from_support_task(doc, prev) -> bool:
	if not doc.source_project_task:
		return False
	if not prev:
		return True
	if prev.status != doc.status:
		return True
	if not _pct_eq(getattr(prev, "project_plan_progress", None), getattr(doc, "project_plan_progress", None)):
		return True
	if (prev.actual_end_date or None) != (doc.actual_end_date or None):
		return True
	return False


def _resolve_progress(doc) -> float | None:
	"""Return a new % for the Project Task, or None to leave the existing value."""
	explicit = getattr(doc, "project_plan_progress", None)
	if explicit is not None and explicit != "":
		try:
			v = float(explicit)
			return max(0.0, min(100.0, v))
		except (TypeError, ValueError):
			pass
	s = doc.status or ""
	if s == "Completed":
		return 100.0
	if s in ("Cancelled", "Open"):
		return 0.0
	return None


def sync_erpnext_task_from_support_task(doc) -> None:
	"""Update linked ERPNext ``Task`` status/progress from this Support Task (best-effort)."""
	if not ENABLE_PROJECT_PLAN_INTEGRATION:
		return
	if getattr(doc, "flags", None) and doc.flags.get("skip_erpnext_task_sync"):
		return
	prev = doc.get_doc_before_save()
	if not _should_sync_from_support_task(doc, prev):
		return

	task_name = doc.source_project_task
	if not frappe.db.exists("Task", task_name):
		return
	if frappe.db.get_value("Task", task_name, "is_group"):
		return

	task = frappe.get_doc("Task", task_name)
	new_status = SUPPORT_TO_TASK_STATUS.get(doc.status, "Working")
	task.status = new_status

	prog = _resolve_progress(doc)
	if prog is not None:
		task.progress = prog

	if new_status == "Completed":
		if doc.actual_end_date:
			task.completed_on = getdate(doc.actual_end_date)
		else:
			task.completed_on = getdate(today())
	else:
		task.completed_on = None

	def _apply_via_set_value():
		fields = {"status": new_status}
		if prog is not None:
			fields["progress"] = flt(prog, 2)
		if new_status == "Completed":
			fields["completed_on"] = task.completed_on
		else:
			fields["completed_on"] = None
		frappe.db.set_value("Task", task_name, fields, update_modified=True)

	try:
		if frappe.has_permission("Task", "write", task_name, user=frappe.session.user):
			task.save()
		else:
			task.save(ignore_permissions=True)
	except frappe.ValidationError as e:
		# ERPNext blocks completing a Task when "Depends on" rows are not done — optional bypass to match Support reality.
		msg = str(e).lower()
		if new_status == "Completed" and ("dependant" in msg or "dependent" in msg):
			_apply_via_set_value()
			frappe.log_error(
				title="Project Task synced via DB update (dependency rule bypassed)",
				message=f"Task {task_name}: {e!s}",
			)
		else:
			frappe.log_error(
				title="Support Task → Project Task sync failed",
				message=frappe.get_traceback(),
			)
	except Exception:
		frappe.log_error(
			title="Support Task → Project Task sync failed",
			message=frappe.get_traceback(),
		)
