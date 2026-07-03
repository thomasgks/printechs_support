# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.printechs_support_system import prai_document_import


class TestPraiDocumentImport(FrappeTestCase):
	def test_parse_json_faqs(self):
		raw = json.dumps(
			{
				"faqs": [
					{
						"title": "How to sync Modern POS",
						"question": "How do I sync Modern POS?",
						"keywords": "sync, modern pos",
						"answer": "<p>Run sync on terminal.</p>",
						"category": "Modern POS",
						"module_area": "Modern POS",
					}
				]
			}
		)
		items = prai_document_import._parse_json_faqs(raw)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["title"], "How to sync Modern POS")

	def test_generate_basic_faqs_from_numbered_text(self):
		text = (
			"1. Setup cashier\n"
			"Create employee and user.\n"
			"Assign POS profile.\n\n"
			"2. Configure barcode\n"
			"Add barcode on item.\n"
			"Sync Modern POS terminal.\n"
		)
		items = prai_document_import.generate_faq_items_from_text(
			text,
			default_category="ERPNext",
			default_module_area="ERPNext",
			use_openai=False,
		)
		self.assertGreaterEqual(len(items), 1)
		self.assertIn("cashier", items[0]["title"].lower())

	def test_upsert_prai_faqs_create_and_update(self):
		title = "PRAI Import Test FAQ"
		if frappe.db.exists("PRAI FAQ", {"title": title}):
			frappe.delete_doc("PRAI FAQ", frappe.db.get_value("PRAI FAQ", {"title": title}, "name"), force=1)

		created = prai_document_import.upsert_prai_faqs(
			[
				{
					"title": title,
					"question": "Test question?",
					"keywords": "test, import",
					"answer": "<p>First answer</p>",
					"category": "General",
					"module_area": "General",
				}
			]
		)
		self.assertEqual(created["created"], 1)
		updated = prai_document_import.upsert_prai_faqs(
			[
				{
					"title": title,
					"question": "Updated question?",
					"keywords": "test, import, updated",
					"answer": "<p>Updated answer</p>",
					"category": "General",
					"module_area": "General",
				}
			],
			update_existing=True,
		)
		self.assertEqual(updated["updated"], 1)
		answer = frappe.db.get_value("PRAI FAQ", {"title": title}, "answer")
		self.assertIn("Updated answer", answer or "")

	def test_generate_with_openai_mock(self):
		payload = json.dumps(
			{
				"faqs": [
					{
						"title": "How to void POS invoice",
						"question": "How can I void a POS sale?",
						"keywords": "void, cancel, pos",
						"answer": "<p><strong>Void invoice</strong></p><ol><li>Open shift</li></ol>",
					}
				]
			}
		)
		with patch(
			"printechs_support.printechs_support_system.api.prai_openai._call_openai_chat",
			return_value=payload,
		):
			with patch(
				"printechs_support.printechs_support_system.prai_document_import.is_openai_configured",
				return_value=True,
			):
				items = prai_document_import.generate_faq_items_from_text(
					"Void invoice procedure for POS cashiers.",
					use_openai=True,
				)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["title"], "How to void POS invoice")

	def test_preview_import_lines_marks_update(self):
		title = "PRAI Import Preview Existing"
		if not frappe.db.exists("PRAI FAQ", {"title": title}):
			frappe.get_doc(
				{
					"doctype": "PRAI FAQ",
					"title": title,
					"question": title,
					"answer": "<p>Existing</p>",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)
		lines = prai_document_import.preview_import_lines(
			[
				{
					"title": title,
					"question": title,
					"keywords": "preview",
					"answer": "<p>New</p>",
					"category": "General",
					"module_area": "General",
				}
			]
		)
		self.assertEqual(lines[0]["action"], "Update")
		self.assertTrue(lines[0]["prai_faq"])
