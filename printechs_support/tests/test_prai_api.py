# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.printechs_support_system.prai_faq_catalog import seed_prai_faqs

# question, phrases that should appear in answer, phrases that must NOT appear
FAQ_ANSWER_CASES = [
	("how to setup a cashier in erpnext", ["cashier", "pos profile"], ["promotion"]),
	("barcode scanner not working on pos", ["scanner", "barcode"], ["promotion"]),
	("how to setup promotion in modern pos", ["promotion", "sync"], ["barcode"]),
	("loyalty points not applying at checkout", ["loyalty", "points"], ["barcode"]),
	("how to top up customer e-wallet", ["wallet", "top"], ["barcode"]),
	("how to sync modern pos with erpnext", ["sync", "modern pos"], ["barcode"]),
	("receipt printer not printing", ["printer"], ["loyalty"]),
	("how to process return or refund on pos", ["refund"], ["promotion"]),
	("payment mode not showing on pos", ["payment", "pos profile"], ["loyalty"]),
	("how to reply to support ticket", ["reply", "ticket"], ["barcode"]),
	("wrong stock quantity on pos", ["stock", "sync"], ["loyalty"]),
	("how to configure pos profile", ["pos profile", "warehouse"], ["barcode"]),
	(
		"how to setup modern pos, please provide me step by step procedure",
		["step", "modern pos", "sync"],
		[],
	),
	(
		"how to add new payment type in modern pos",
		["mode of payment", "pos profile", "sync"],
		["stock item", "custom_is_pos", "barcode"],
	),
	(
		"what is the procedure to push a new item into modern pos",
		["stock item", "custom_is_pos", "item price", "sync"],
		["terminal install"],
	),
	("customer not found at checkout", ["customer", "sync"], ["printer"]),
	("how to open and close pos shift", ["shift", "closing"], ["barcode"]),
	("how to view sales report from pos", ["sales", "report"], ["barcode"]),
]


class TestPraiApi(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_prai_faqs(update_existing=True)

	def setUp(self):
		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 1
		settings.save(ignore_permissions=True)
		frappe.set_user("Administrator")

	def tearDown(self):
		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 0
		settings.save(ignore_permissions=True)
		frappe.set_user("Administrator")

	def test_catalog_seeded(self):
		count = frappe.db.count("PRAI FAQ", {"is_active": 1})
		self.assertGreaterEqual(count, 25)

	def test_faq_questions_return_relevant_answers(self):
		from printechs_support.printechs_support_system.api import prai_api

		for question, must_include, must_exclude in FAQ_ANSWER_CASES:
			with self.subTest(question=question):
				result = prai_api.prai_ask(question)
				content = ((result.get("message") or {}).get("content") or "").lower()
				self.assertFalse(result.get("suggest_escalation"), msg=f"No match for: {question}")
				for phrase in must_include:
					self.assertIn(phrase, content, msg=f"Expected '{phrase}' in answer for: {question}")
				for phrase in must_exclude:
					self.assertNotIn(phrase, content, msg=f"Unexpected '{phrase}' in answer for: {question}")

	def test_format_answer_for_chat_numbered_steps(self):
		from printechs_support.printechs_support_system.api.prai_api import _format_answer_for_chat

		html = (
			"<p><strong>Procedure to push a new item to Modern POS</strong></p>"
			"<ol>"
			"<li><strong>Stock Item</strong> — Enable Stock Item.</li>"
			"<li><strong>POS flag</strong> — Enable Is POS (<code>custom_is_pos</code>).</li>"
			"</ol>"
			"<p>If the item still does not appear, confirm the item is not disabled.</p>"
		)
		formatted = _format_answer_for_chat(html)
		self.assertIn("1. Stock Item — Enable Stock Item.", formatted)
		self.assertIn("2. POS flag — Enable Is POS (custom_is_pos).", formatted)
		self.assertIn("\n\n", formatted)
		self.assertIn("If the item still does not appear", formatted)

	def test_push_item_faq_answer_is_formatted(self):
		from printechs_support.printechs_support_system.api import prai_api

		result = prai_api.prai_ask("what is the procedure to push a new item into modern pos")
		content = (result.get("message") or {}).get("content") or ""
		self.assertIn("1. Stock Item", content)
		self.assertIn("7. Test", content)
		self.assertIn("\n", content)

	def test_unknown_question_suggests_ticket_not_openai(self):
		from printechs_support.printechs_support_system.api import prai_api

		result = prai_api.prai_ask("explain quantum widget calibration on retail shelf")
		message = result.get("message") or {}
		self.assertEqual(message.get("source_type"), "System")
		self.assertIn("support ticket", (message.get("content") or "").lower())
		self.assertTrue(result.get("suggest_escalation"))
		self.assertNotEqual(message.get("source_type"), "OpenAI")

	def test_payment_type_question_not_item_faq(self):
		from printechs_support.printechs_support_system.api import prai_api

		q = "how to add new Payment Type in Modern POS"
		match = prai_api._match_faq(q)
		self.assertTrue(match)
		self.assertIn("payment", match[0][1].title.lower())
		self.assertNotIn("push a new item", match[0][1].title.lower())

	def test_general_product_question_skips_faq(self):
		from printechs_support.printechs_support_system.api import prai_api

		self.assertEqual(prai_api._match_faq("What is ERPNEXT?"), [])

	def test_prai_ask_unknown_suggests_escalation(self):
		from printechs_support.printechs_support_system.api import prai_api

		result = prai_api.prai_ask("zzzz completely unknown question about quantum widgets")
		self.assertTrue(result.get("success"))
		self.assertTrue(result.get("suggest_escalation"))

	def test_prai_disabled_rejects_ask(self):
		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 0
		settings.save(ignore_permissions=True)
		from printechs_support.printechs_support_system.api import prai_api

		with self.assertRaises(frappe.ValidationError):
			prai_api.prai_ask("hello")

	def test_escalate_creates_ticket(self):
		from printechs_support.printechs_support_system.api import prai_api

		ask = prai_api.prai_ask("barcode scanner pos help")
		session_id = ask["session"]["name"]
		escalated = prai_api.escalate_prai_to_ticket(session_id)
		self.assertTrue(escalated.get("success"))
		ticket_id = escalated.get("ticket_id")
		self.assertTrue(ticket_id)
		self.assertTrue(frappe.db.exists("Support Ticket", ticket_id))
		session = frappe.get_doc("PRAI Chat Session", session_id)
		self.assertEqual(session.support_ticket, ticket_id)
