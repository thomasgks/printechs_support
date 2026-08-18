# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from printechs_support.prai_studio.health_rule_service import run_health_checks
from printechs_support.prai_studio.help_article_generation_service import (
	draft_help_lines_from_items,
	generate_draft_help_articles_from_findings,
)
from printechs_support.prai_studio.knowledge_generation_service import (
	draft_lines_from_faq_items,
	generate_draft_faqs_from_findings,
)
from printechs_support.prai_studio.permissions import (
	user_can_publish_studio,
	user_can_review_studio,
	user_can_upload_source,
)
from printechs_support.prai_studio.publish_service import publish_approved_knowledge
from printechs_support.prai_studio.source_analyzer_service import analyze_scan_run, build_analysis_summary


class PRAIStudioKnowledgeRun(Document):
	@frappe.whitelist()
	def run_analysis(self):
		if not user_can_upload_source():
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		self.status = "Analyzing"
		self.analysis_log = ""
		self.save(ignore_permissions=True)
		frappe.db.commit()

		try:
			findings = analyze_scan_run(self.source_scan_run)
			self.analysis_findings = []
			for row in findings:
				self.append("analysis_findings", row)
			self.analysis_summary = build_analysis_summary(findings)
			self.status = "Analyzed"
			self.analysis_log = _("Analysis completed: {0} finding(s).").format(len(findings))
			self.save(ignore_permissions=True)
			frappe.db.commit()
			return {"success": True, "status": self.status, "findings": len(findings)}
		except Exception as exc:
			frappe.db.rollback()
			self.reload()
			self.status = "Failed"
			self.analysis_log = str(exc)
			self.save(ignore_permissions=True)
			frappe.db.commit()
			raise

	@frappe.whitelist()
	def run_health_checks_action(self):
		if not user_can_upload_source():
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		results = run_health_checks(source_project=self.source_project)
		self.health_check_results = []
		warnings = 0
		for row in results:
			self.append("health_check_results", row)
			if row.get("result_status") in {"Warning", "Fail"}:
				warnings += 1
		self.health_check_log = _("Health checks completed: {0} rule(s), {1} warning/fail.").format(
			len(results), warnings
		)
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "rules": len(results), "warnings": warnings}

	@frappe.whitelist()
	def generate_faqs(self):
		if not user_can_upload_source():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if self.status not in {"Analyzed", "Generated", "In Review"}:
			frappe.throw(_("Run analysis before generating FAQs."), frappe.ValidationError)

		self.status = "Generating"
		self.save(ignore_permissions=True)
		frappe.db.commit()

		try:
			findings = [row.as_dict() for row in self.analysis_findings or []]
			health = [row.as_dict() for row in self.health_check_results or []]
			items = generate_draft_faqs_from_findings(
				findings,
				default_category=self.default_category or "General",
				default_module_area=self.default_module_area or "General",
				use_openai=cint(self.use_openai),
				product_name=self.product_name or "Modern POS",
			)
			self.draft_items = []
			for row in draft_lines_from_faq_items(items):
				self.append("draft_items", row)

			help_count = 0
			if cint(self.generate_help_articles):
				help_items = generate_draft_help_articles_from_findings(
					findings,
					help_category=self.default_help_category or "ERPNext Basics",
					module_area=self.default_module_area or "ERPNext",
					product_name=self.product_name or "Modern POS",
					health_results=health,
				)
				self.draft_help_items = []
				for row in draft_help_lines_from_items(help_items):
					self.append("draft_help_items", row)
				help_count = len(self.draft_help_items)

			self.status = "Generated"
			self.generation_log = _(
				"Generated {0} draft FAQ(s) and {1} draft Help Article(s). Review, submit, approve, then publish."
			).format(len(self.draft_items), help_count)
			self.save(ignore_permissions=True)
			frappe.db.commit()
			return {
				"success": True,
				"status": self.status,
				"generated": len(self.draft_items),
				"help_generated": help_count,
			}
		except Exception as exc:
			frappe.db.rollback()
			self.reload()
			self.status = "Failed"
			self.generation_log = str(exc)
			self.save(ignore_permissions=True)
			frappe.db.commit()
			raise

	@frappe.whitelist()
	def generate_help_articles(self):
		if not user_can_upload_source():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if not self.analysis_findings:
			frappe.throw(_("Run analysis before generating Help Articles."), frappe.ValidationError)

		findings = [row.as_dict() for row in self.analysis_findings or []]
		health = [row.as_dict() for row in self.health_check_results or []]
		help_items = generate_draft_help_articles_from_findings(
			findings,
			help_category=self.default_help_category or "ERPNext Basics",
			module_area=self.default_module_area or "ERPNext",
			product_name=self.product_name or "Modern POS",
			health_results=health,
		)
		self.draft_help_items = []
		for row in draft_help_lines_from_items(help_items):
			self.append("draft_help_items", row)
		self.generation_log = (self.generation_log or "") + "\n" + _(
			"Generated {0} draft Help Article(s)."
		).format(len(self.draft_help_items))
		if self.status == "Analyzed":
			self.status = "Generated"
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "help_generated": len(self.draft_help_items)}

	@frappe.whitelist()
	def submit_for_review(self):
		if not user_can_upload_source():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if not self.draft_items and not self.draft_help_items:
			frappe.throw(_("Generate draft content first."), frappe.ValidationError)

		faq_count = _submit_table_for_review(self, "draft_items")
		help_count = _submit_table_for_review(self, "draft_help_items")
		total = faq_count + help_count
		if not total:
			frappe.throw(_("Select at least one draft row to submit."), frappe.ValidationError)

		self.status = "In Review"
		self.generation_log = (self.generation_log or "") + "\n" + _(
			"Submitted {0} FAQ(s) and {1} Help Article(s) for review."
		).format(faq_count, help_count)
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "status": self.status, "submitted": total, "faq_count": faq_count, "help_count": help_count}

	@frappe.whitelist()
	def approve_selected(self):
		if not user_can_review_studio():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		faq_count = _set_table_review_status(self, "draft_items", "Approved")
		help_count = _set_table_review_status(self, "draft_help_items", "Approved")
		count = faq_count + help_count
		if not count:
			frappe.throw(_("No eligible draft rows were selected."), frappe.ValidationError)
		self.generation_log = (self.generation_log or "") + "\n" + _(
			"Approved {0} FAQ(s) and {1} Help Article(s)."
		).format(faq_count, help_count)
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "approved": count, "faq_count": faq_count, "help_count": help_count}

	@frappe.whitelist()
	def reject_selected(self):
		if not user_can_review_studio():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		faq_count = _set_table_review_status(self, "draft_items", "Rejected")
		help_count = _set_table_review_status(self, "draft_help_items", "Rejected")
		count = faq_count + help_count
		if not count:
			frappe.throw(_("No eligible draft rows were selected."), frappe.ValidationError)
		self.generation_log = (self.generation_log or "") + "\n" + _(
			"Rejected {0} FAQ(s) and {1} Help Article(s)."
		).format(faq_count, help_count)
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "rejected": count}

	@frappe.whitelist()
	def publish_approved(self):
		if not user_can_publish_studio():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return publish_approved_knowledge(self.name)


@frappe.whitelist()
def create_knowledge_run_from_scan(source_scan_run: str) -> dict:
	if not user_can_upload_source():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	scan = frappe.get_doc("PRAI Source Scan Run", source_scan_run)
	if scan.status != "Extracted":
		frappe.throw(_("Scan run must be Extracted before creating a knowledge run."), frappe.ValidationError)

	project = frappe.get_doc("PRAI Source Project", scan.source_project)
	existing = frappe.db.get_value(
		"PRAI Studio Knowledge Run",
		{"source_scan_run": scan.name, "status": ("not in", ["Published", "Failed"])},
		"name",
	)
	if existing:
		return {"success": True, "name": existing, "existing": True}

	run = frappe.get_doc(
		{
			"doctype": "PRAI Studio Knowledge Run",
			"source_project": scan.source_project,
			"source_scan_run": scan.name,
			"product_name": project.product_name or "Modern POS",
			"product_version": project.product_version,
			"default_category": "Modern POS",
			"default_module_area": "Modern POS",
			"default_help_category": "ERPNext Basics",
			"generate_help_articles": 1,
			"status": "Draft",
		}
	)
	run.insert(ignore_permissions=True)
	frappe.db.set_value("PRAI Source Scan Run", scan.name, "latest_knowledge_run", run.name)
	frappe.db.commit()
	return {"success": True, "name": run.name, "existing": False}


def _submit_table_for_review(doc, table_field: str) -> int:
	count = 0
	for row in doc.get(table_field) or []:
		if not cint(row.include):
			continue
		row.review_status = "Pending Review"
		count += 1
	return count


def _set_table_review_status(doc, table_field: str, status: str) -> int:
	count = 0
	for row in doc.get(table_field) or []:
		if not cint(row.include):
			continue
		current = row.review_status or "Draft"
		if current != "Pending Review":
			continue
		row.review_status = status
		count += 1
	return count
