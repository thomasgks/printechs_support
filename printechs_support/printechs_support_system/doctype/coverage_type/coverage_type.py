# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CoverageType(Document):
	def validate(self):
		title = (self.title or "").strip()
		if not title:
			return
		existing = frappe.db.get_value(
			"Coverage Type",
			{"division": self.division, "title": title},
			"name",
		)
		if existing and existing != self.name:
			frappe.throw(
				_("A coverage type named {0} already exists for division {1}.").format(
					title, self.division or ""
				),
				title=_("Duplicate"),
			)
