# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.prai_studio.doctype.prai_studio_knowledge_run.prai_studio_knowledge_run import (
	create_knowledge_run_from_scan,
)
from printechs_support.prai_studio.knowledge_generation_service import generate_draft_faqs_from_findings
from printechs_support.prai_studio.source_analyzer_service import analyze_scan_run, build_analysis_summary
from printechs_support.prai_studio.zip_extraction_service import studio_extract_root


class TestPraiStudioPhase2(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._cleanup_names: list[tuple[str, str]] = []

	def tearDown(self):
		for doctype, name in reversed(self._cleanup_names):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=1)
		super().tearDown()

	def _track(self, doctype: str, name: str) -> None:
		self._cleanup_names.append((doctype, name))

	def _create_extracted_scan_run(self) -> str:
		project = frappe.get_doc(
			{
				"doctype": "PRAI Source Project",
				"project_name": "Phase2 Test Project",
				"product_name": "Modern POS",
				"source_zip": "/private/files/phase2_dummy.zip",
				"status": "Extracted",
			}
		)
		project.insert(ignore_permissions=True)
		self._track("PRAI Source Project", project.name)

		root = studio_extract_root(project.name) / "source"
		root.mkdir(parents=True, exist_ok=True)
		(root / "PromotionService.cs").write_text(
			"class PromotionService { public void ApplyPromotion() { var promotion = true; } }",
			encoding="utf-8",
		)
		(root / "schema.sql").write_text("CREATE TABLE pos_promotion (name varchar(120));", encoding="utf-8")
		(root / "README.md").write_text("# Modern POS\n## Promotion setup\nEnable promotion sync.", encoding="utf-8")

		scan = frappe.get_doc(
			{
				"doctype": "PRAI Source Scan Run",
				"source_project": project.name,
				"status": "Extracted",
				"extracted_path": str(root),
				"scan_files": [
					{
						"file_path": "PromotionService.cs",
						"file_name": "PromotionService.cs",
						"extension": ".cs",
						"file_size": 120,
						"scan_category": "Promotion",
					},
					{
						"file_path": "schema.sql",
						"file_name": "schema.sql",
						"extension": ".sql",
						"file_size": 80,
						"scan_category": "Database",
					},
					{
						"file_path": "README.md",
						"file_name": "README.md",
						"extension": ".md",
						"file_size": 60,
						"scan_category": "Documentation",
					},
				],
			}
		)
		scan.insert(ignore_permissions=True)
		self._track("PRAI Source Scan Run", scan.name)
		return scan.name

	def test_analyze_scan_run_finds_promotion_and_sql(self):
		scan_name = self._create_extracted_scan_run()
		findings = analyze_scan_run(scan_name)
		titles = " ".join(row["title"] for row in findings).lower()
		self.assertIn("promotion", titles)
		self.assertIn("pos_promotion", titles)
		summary = build_analysis_summary(findings)
		self.assertIn("Promotion", summary)

	def test_generate_basic_draft_faqs_without_openai(self):
		findings = [
			{
				"finding_type": "Promotion",
				"title": "Feature class: PromotionService",
				"file_path": "PromotionService.cs",
				"summary": "Defined in PromotionService.cs",
				"detail": "class PromotionService",
				"scan_category": "Promotion",
			}
		]
		items = generate_draft_faqs_from_findings(
			findings,
			default_category="Modern POS",
			default_module_area="Modern POS",
			use_openai=False,
		)
		self.assertGreaterEqual(len(items), 1)
		self.assertIn("PromotionService", items[0]["title"])

	def test_knowledge_run_end_to_end_without_openai(self):
		scan_name = self._create_extracted_scan_run()
		created = create_knowledge_run_from_scan(scan_name)
		self.assertTrue(created["success"])
		run_name = created["name"]
		self._track("PRAI Studio Knowledge Run", run_name)

		run = frappe.get_doc("PRAI Studio Knowledge Run", run_name)
		analysis = run.run_analysis()
		self.assertTrue(analysis["success"])
		self.assertGreater(analysis["findings"], 0)

		run.reload()
		run.use_openai = 0
		generated = run.generate_faqs()
		self.assertTrue(generated["success"])
		self.assertGreater(generated["generated"], 0)

		run.reload()
		submitted = run.submit_for_review()
		self.assertTrue(submitted["success"])
		self.assertEqual(run.status, "In Review")

		run.reload()
		approved = run.approve_selected()
		self.assertTrue(approved["success"])

		run.reload()
		published = run.publish_approved()
		self.assertTrue(published["success"])
		self.assertTrue(frappe.db.exists("PRAI Publish Log", published["publish_log"]))
		self.assertTrue(frappe.db.exists("PRAI FAQ", {"title": run.draft_items[0].title}))
