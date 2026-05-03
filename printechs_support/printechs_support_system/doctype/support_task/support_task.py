# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime

from printechs_support.assignee_sync import sync_user_assignee_rows


_VALID_DIVISIONS = frozenset({"Software", "Industrial", "Retail"})


class SupportTask(Document):
	def validate(self):
		self.validate_standalone_internal()
		self.validate_source_project_task_unique()
		self.validate_predecessor()
		self.sync_from_ticket()
		self.sync_task_assignees()
		self.ensure_schedule_defaults()
		self.update_delay_fields()

	def validate_standalone_internal(self):
		"""Support Ticket is optional; internal standalone tasks must have Division set."""
		if self.support_ticket:
			return
		d = (self.division or "").strip()
		if not d or d not in _VALID_DIVISIONS:
			frappe.throw(
				_("Division is required when Support Ticket is not set (Software, Industrial, or Retail)."),
				frappe.ValidationError,
			)

	def validate_source_project_task_unique(self):
		if not self.source_project_task:
			return
		other = frappe.db.exists(
			"Support Task",
			{"source_project_task": self.source_project_task, "name": ["!=", self.name or ""]},
		)
		if other:
			frappe.throw(
				_("Project plan task {0} is already linked to Support Task {1}.").format(
					self.source_project_task, other
				)
			)
		if self.project:
			pt_proj = frappe.db.get_value("Task", self.source_project_task, "project")
			if pt_proj and pt_proj != self.project:
				frappe.throw(_("Project plan task must belong to the same Project as this Support Task."))

	def after_insert(self):
		from printechs_support.project_task_sync import sync_erpnext_task_from_support_task

		sync_erpnext_task_from_support_task(self)

	def on_update(self):
		from printechs_support.project_task_sync import sync_erpnext_task_from_support_task

		sync_erpnext_task_from_support_task(self)

		if self.flags.get("skip_due_sync"):
			return
		prev = self.get_doc_before_save()
		if not prev or not self.support_ticket:
			return
		if (prev.due_date or None) == (self.due_date or None):
			return
		from printechs_support.due_date_sync import sync_support_ticket_due_from_task

		sync_support_ticket_due_from_task(self.name)

	def sync_task_assignees(self):
		sync_user_assignee_rows(self, child_field="task_assignees", primary_field="assigned_to_user")

	def validate_predecessor(self):
		if not self.predecessor_task:
			self.depends_on_tasks = ""
			return
		if self.name and self.predecessor_task == self.name:
			frappe.throw(_("Predecessor cannot be the same task."))
		pred = frappe.db.get_value(
			"Support Task",
			self.predecessor_task,
			["support_ticket", "name"],
			as_dict=True,
		)
		if not pred:
			frappe.throw(_("Invalid predecessor task."))
		if (self.support_ticket or None) != (pred.support_ticket or None):
			frappe.throw(
				_("Predecessor must be on the same Support Ticket, or both tasks must be internal-only (no ticket).")
			)
		self.depends_on_tasks = pred.name

	def ensure_schedule_defaults(self):
		if self.planned_start_date and not self.planned_end_date:
			self.planned_end_date = add_to_date(self.planned_start_date, days=1, as_datetime=True)

	def sync_from_ticket(self):
		if not self.support_ticket:
			return
		t = frappe.db.get_value(
			"Support Ticket",
			self.support_ticket,
			["customer", "support_agreement", "division"],
			as_dict=True,
		)
		if not t:
			return
		if t.customer:
			self.customer = t.customer
		if t.support_agreement:
			self.support_agreement = t.support_agreement
		if t.division:
			self.division = t.division

	def update_delay_fields(self):
		self.delay_days = 0.0
		if self.due_date and self.actual_end_date:
			due = get_datetime(self.due_date)
			end = get_datetime(self.actual_end_date)
			if end > due:
				self.is_delayed = 1
				self.delay_days = (end - due).total_seconds() / 86400.0
			else:
				self.is_delayed = 0

		if self.status == "Delayed":
			if not self.delay_owner or not self.delay_reason or not (self.delay_remarks or "").strip():
				frappe.throw(_("Delay Owner, Delay Reason, and Delay Remarks are required when status is Delayed."))
