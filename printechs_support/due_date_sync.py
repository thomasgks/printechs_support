# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Keep Support Ticket `due_date` and Support Task `due_date` aligned."""

import frappe


def sync_support_ticket_due_from_task(task_name: str) -> None:
	"""After a Support Task `due_date` changes, set parent Support Ticket `due_date` to the same value.

	Uses Document.save() so ``track_changes`` / Version history records the ticket change (reports / audit).
	"""
	row = frappe.db.get_value(
		"Support Task",
		task_name,
		["support_ticket", "due_date"],
		as_dict=True,
	)
	if not row or not row.support_ticket:
		return
	ticket = frappe.get_doc("Support Ticket", row.support_ticket)
	if (ticket.due_date or None) == (row.due_date or None):
		return
	ticket.due_date = row.due_date
	ticket.flags.ignore_permissions = True
	# Task due edits must not push the same date onto every sibling task on the ticket.
	ticket.flags.skip_propagate_due_to_tasks = True
	ticket.save()


def propagate_support_ticket_due_to_tasks(ticket_name: str, due_date) -> None:
	"""When Support Ticket `due_date` is set (e.g. manager on Desk or portal), push to all non-cancelled tasks."""
	frappe.db.sql(
		"""
		UPDATE `tabSupport Task`
		SET `due_date` = %s
		WHERE `support_ticket` = %s AND IFNULL(`status`, '') != 'Cancelled'
		""",
		(due_date, ticket_name),
	)
