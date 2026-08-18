# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class PRAISourceScanRun(Document):
	@frappe.whitelist()
	def create_knowledge_run(self):
		from printechs_support.prai_studio.doctype.prai_studio_knowledge_run.prai_studio_knowledge_run import (
			create_knowledge_run_from_scan,
		)

		return create_knowledge_run_from_scan(self.name)
