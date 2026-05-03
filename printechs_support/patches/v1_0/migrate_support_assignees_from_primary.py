# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Backfill Task/Ticket assignee child tables from legacy single primary User fields."""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Support Task Assignee"):
		return

	for name in frappe.get_all(
		"Support Task",
		filters={"assigned_to_user": ["!=", ""]},
		pluck="name",
	):
		if frappe.db.count("Support Task Assignee", {"parent": name}):
			continue
		doc = frappe.get_doc("Support Task", name)
		doc.append("task_assignees", {"user": doc.assigned_to_user, "is_primary": 1})
		doc.flags.ignore_permissions = True
		doc.save()

	if not frappe.db.exists("DocType", "Support Ticket Assignee"):
		return

	for name in frappe.get_all(
		"Support Ticket",
		filters={"assigned_to": ["!=", ""]},
		pluck="name",
	):
		if frappe.db.count("Support Ticket Assignee", {"parent": name}):
			continue
		doc = frappe.get_doc("Support Ticket", name)
		doc.append("ticket_assignees", {"user": doc.assigned_to, "is_primary": 1})
		doc.flags.ignore_permissions = True
		doc.save()

	frappe.db.commit()
