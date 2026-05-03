# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document


class SupportTeam(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING, Literal

	if TYPE_CHECKING:
		from frappe.types import DF

		default_email: DF.Data | None
		division: Literal["Software", "Industrial", "Retail"]
		is_active: DF.Check
		team_lead: DF.Link | None
		team_lead_email: DF.Data | None
		team_lead_name: DF.Data | None
		team_name: DF.Data
	# end: auto-generated types

	def validate(self):
		users = [r.user for r in (self.team_members or []) if getattr(r, "user", None)]
		if len(users) != len(set(users)):
			frappe.throw(_("Each user can appear only once in team members."))

		# If company email is blank on Employee, use preferred/personal email for display.
		if not self.team_lead:
			return
		if self.team_lead_email:
			return
		if not frappe.db.exists("DocType", "Employee"):
			return
		emp = frappe.db.get_value(
			"Employee",
			self.team_lead,
			["prefered_email", "personal_email"],
			as_dict=True,
		)
		if not emp:
			return
		self.team_lead_email = (emp.prefered_email or emp.personal_email or "").strip() or None
