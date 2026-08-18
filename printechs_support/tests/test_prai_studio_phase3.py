# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.prai_studio.health_rule_service import (
	ensure_default_health_rule_templates,
	run_health_checks,
)
from printechs_support.prai_studio.help_article_generation_service import (
	generate_draft_help_articles_from_findings,
	upsert_help_articles,
)
from printechs_support.prai_studio.source_analyzer_service import _analyze_cs_deep


class TestPraiStudioPhase3(FrappeTestCase):
	def test_default_health_rule_templates_seeded(self):
		ensure_default_health_rule_templates()
		self.assertTrue(frappe.db.exists("PRAI Studio Health Rule Template", "PROMO-NOT-ON-POS"))

	def test_run_health_checks_returns_results(self):
		ensure_default_health_rule_templates()
		results = run_health_checks()
		self.assertGreaterEqual(len(results), 3)
		self.assertTrue(all(row.get("rule_key") for row in results))

	def test_cs_deep_analyzer_finds_namespace_and_api(self):
		content = (
			"namespace ModernPos.Api {\n"
			"  [HttpGet(\"promotions\")]\n"
			"  public class PromotionController : ApiController {\n"
			"    public void SyncPromotions() {}\n"
			"  }\n"
			"}"
		)
		findings = _analyze_cs_deep("Api/PromotionController.cs", content, "Api")
		titles = " ".join(row["title"] for row in findings).lower()
		self.assertIn("namespace", titles)
		self.assertIn("api", titles)

	def test_generate_help_articles_from_findings(self):
		findings = [
			{
				"finding_type": "Documentation",
				"title": "Doc topic: Promotion setup",
				"file_path": "README.md",
				"summary": "From README.md",
				"detail": "Enable promotion sync on terminal after ERPNext configuration.",
			}
		]
		items = generate_draft_help_articles_from_findings(
			findings,
			help_category="ERPNext Basics",
			module_area="ERPNext",
			product_name="Modern POS",
		)
		self.assertGreaterEqual(len(items), 1)
		self.assertEqual(items[0].get("help_category"), "ERPNext Basics")

	def test_upsert_help_articles_create(self):
		title = "PRAI Studio Phase3 Test Article"
		category = "ERPNext Basics"
		if frappe.db.exists("Help Article", {"title": title, "category": category}):
			frappe.delete_doc(
				"Help Article",
				frappe.db.get_value("Help Article", {"title": title, "category": category}, "name"),
				force=1,
			)
		result = upsert_help_articles(
			[
				{
					"title": title,
					"summary": "Test summary",
					"keywords": "phase3, studio",
					"content": "<p>Phase 3 help article test.</p>",
					"help_category": category,
					"module_area": "ERPNext",
				}
			]
		)
		self.assertEqual(result["created"], 1)
		name = frappe.db.get_value("Help Article", {"title": title, "category": category}, "name")
		self.assertTrue(name)
		doc = frappe.get_doc("Help Article", name)
		self.assertEqual(doc.status, "Published")
		frappe.delete_doc("Help Article", name, force=1)
