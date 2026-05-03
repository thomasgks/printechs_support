# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Extend ERPNext Project form connections with Printechs Support doc types."""

import frappe
from frappe import _


def extend_project_dashboard(data=None):
	"""Merge Printechs Support links into Project dashboard (uses `project` link field)."""
	data = frappe._dict(data or {})
	if not data.get("transactions"):
		data.transactions = []
	data.transactions.append(
		{
			"label": _("Printechs Support"),
			"items": ["Support Task", "Support Ticket"],
		}
	)
	return data
