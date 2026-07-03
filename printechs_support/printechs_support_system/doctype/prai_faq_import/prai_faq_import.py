# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from printechs_support.printechs_support_system.prai_document_import import (
	process_import_document,
	upsert_prai_faqs,
)


class PRAIFAQImport(Document):
	def validate(self):
		if self.import_file:
			self.file_name = (self.import_file or "").split("/")[-1]

	@frappe.whitelist()
	def extract_document(self):
		frappe.only_for(("System Manager", "Printechs Support Coordinator"))
		return process_import_document(self.name, step="extract")

	@frappe.whitelist()
	def generate_preview(self):
		frappe.only_for(("System Manager", "Printechs Support Coordinator"))
		return process_import_document(self.name, step="preview")

	@frappe.whitelist()
	def import_selected_faqs(self):
		frappe.only_for(("System Manager", "Printechs Support Coordinator"))
		doc = frappe.get_doc("PRAI FAQ Import", self.name)
		selected = []
		for row in doc.items or []:
			if not cint(row.include):
				continue
			if not (row.title or "").strip() or not (row.answer or "").strip():
				continue
			selected.append(
				{
					"title": row.title,
					"question": row.question or row.title,
					"keywords": row.keywords or "",
					"answer": row.answer,
					"category": row.category or doc.default_category or "General",
					"module_area": row.module_area or doc.default_module_area or "General",
				}
			)
		if not selected:
			frappe.throw(_("Select at least one generated FAQ row to import."), frappe.ValidationError)

		result = upsert_prai_faqs(selected, update_existing=cint(doc.update_existing))
		doc.status = "Imported"
		doc.import_log = _(
			"Imported FAQs — created: {created}, updated: {updated}, skipped: {skipped}"
		).format(**result)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "status": doc.status, **result}
