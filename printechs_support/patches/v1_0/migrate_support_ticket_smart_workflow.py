# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Map legacy Support Ticket status values to the smart workflow vocabulary."""

import frappe


def execute():
	status_map = {
		"Draft": "Open",
		"Acknowledged": "Assigned",
		"Waiting for Internal Team": "Waiting for Technician",
		"Waiting for Approval": "Open",
		"Reopened": "In Progress",
	}
	for old, new in status_map.items():
		frappe.db.sql(
			"UPDATE `tabSupport Ticket` SET status=%s WHERE status=%s",
			(new, old),
		)

	frappe.db.sql(
		"""
		UPDATE `tabSupport Ticket`
		SET action_required_from = CASE `status`
			WHEN 'Waiting for Customer' THEN 'Customer'
			WHEN 'Waiting for Technician' THEN 'Technician'
			WHEN 'In Progress' THEN 'Technician'
			WHEN 'Assigned' THEN 'Technician'
			WHEN 'Resolved' THEN 'Customer'
			WHEN 'Closed' THEN 'None'
			WHEN 'Cancelled' THEN 'None'
			ELSE 'Manager'
		END,
		current_owner_type = CASE `status`
			WHEN 'Waiting for Customer' THEN 'Customer'
			WHEN 'Waiting for Technician' THEN 'Technician'
			WHEN 'In Progress' THEN 'Technician'
			WHEN 'Assigned' THEN 'Technician'
			WHEN 'Resolved' THEN 'Customer'
			WHEN 'Closed' THEN 'None'
			WHEN 'Cancelled' THEN 'None'
			ELSE 'Manager'
		END
		"""
	)
