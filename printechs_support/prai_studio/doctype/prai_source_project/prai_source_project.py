# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from __future__ import annotations

from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from printechs_support.prai_studio.permissions import user_can_upload_source
from printechs_support.prai_studio.source_scanner_service import scan_extracted_tree
from printechs_support.prai_studio.zip_extraction_service import extract_source_zip


class PRAISourceProject(Document):
	def validate(self):
		if self.source_zip:
			name = (self.source_zip or "").split("/")[-1]
			self.zip_file_name = name
			if name and not name.lower().endswith(".zip"):
				frappe.throw(_("Only .zip files are allowed."), frappe.ValidationError)
		if not self.uploaded_by:
			self.uploaded_by = frappe.session.user
		if not self.uploaded_date:
			self.uploaded_date = now_datetime()
		if self.source_zip and self.status == "Draft":
			self.status = "Uploaded"

	@frappe.whitelist()
	def extract_and_scan(self):
		if not user_can_upload_source():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if not self.source_zip:
			frappe.throw(_("Attach a ZIP file before scanning."), frappe.ValidationError)

		self.status = "Extracting"
		self.scan_log = ""
		self.save(ignore_permissions=True)
		frappe.db.commit()

		scan_run = frappe.get_doc(
			{
				"doctype": "PRAI Source Scan Run",
				"source_project": self.name,
				"status": "Extracting",
				"started_at": now_datetime(),
			}
		)
		scan_run.insert(ignore_permissions=True)

		try:
			extract_dir, extract_log = extract_source_zip(file_url=self.source_zip, project_name=self.name)
			file_rows = scan_extracted_tree(extract_dir)
			root = Path(extract_dir)
			scan_run.extracted_path = extract_dir
			scan_run.total_files = sum(1 for p in root.rglob("*") if p.is_file())
			scan_run.scanned_files = len(file_rows)
			scan_run.scan_files = []
			for row in file_rows:
				scan_run.append("scan_files", row)
			scan_run.status = "Extracted"
			scan_run.completed_at = now_datetime()
			scan_run.scan_log = "\n".join(extract_log)
			scan_run.save(ignore_permissions=True)

			self.status = "Extracted"
			self.latest_scan_run = scan_run.name
			self.scan_log = scan_run.scan_log
			self.save(ignore_permissions=True)
			frappe.db.commit()
			return {
				"success": True,
				"status": self.status,
				"scan_run": scan_run.name,
				"scanned_files": scan_run.scanned_files,
			}
		except Exception as exc:
			frappe.db.rollback()
			scan_run.reload()
			scan_run.status = "Failed"
			scan_run.completed_at = now_datetime()
			scan_run.scan_log = str(exc)
			scan_run.save(ignore_permissions=True)
			self.reload()
			self.status = "Scan Failed"
			self.scan_log = str(exc)
			self.latest_scan_run = scan_run.name
			self.save(ignore_permissions=True)
			frappe.db.commit()
			raise
