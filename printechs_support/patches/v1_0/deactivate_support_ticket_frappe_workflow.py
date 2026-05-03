# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Disable Frappe Workflow on Support Ticket — conflicts with Python smart workflow (ticket_workflow)."""

import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabWorkflow`
		SET `is_active` = 0
		WHERE `document_type` = %s AND IFNULL(`is_active`, 0) = 1
		""",
		("Support Ticket",),
	)
