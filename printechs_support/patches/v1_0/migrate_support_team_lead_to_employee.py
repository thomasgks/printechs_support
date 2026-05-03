# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Map Support Team.team_lead from User (legacy) to Employee via Employee.user_id."""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Employee"):
		return

	for row in frappe.get_all("Support Team", fields=["name", "team_lead"]):
		lead = (row.team_lead or "").strip()
		if not lead:
			continue
		if frappe.db.exists("Employee", lead):
			continue
		if not frappe.db.exists("User", lead):
			continue
		emp = frappe.db.get_value("Employee", {"user_id": lead}, "name")
		if emp:
			frappe.db.set_value("Support Team", row.name, "team_lead", emp)
		else:
			frappe.db.set_value("Support Team", row.name, "team_lead", None)

	frappe.db.commit()
