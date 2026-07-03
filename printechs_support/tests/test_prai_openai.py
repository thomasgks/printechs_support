# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

from printechs_support.printechs_support_system.api import prai_openai
from printechs_support.printechs_support_system.prai_faq_catalog import seed_prai_faqs


class TestPraiOpenAI(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_prai_faqs(update_existing=True)

	def setUp(self):
		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 1
		settings.enable_openai = 1
		settings.enable_openai_chat = 1
		settings.openai_model = "gpt-4o-mini"
		settings.openai_api_key = "sk-test-key"
		settings.save(ignore_permissions=True)
		frappe.set_user("Administrator")

	def tearDown(self):
		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 0
		settings.enable_openai = 0
		settings.enable_openai_chat = 0
		settings.openai_api_key = ""
		settings.save(ignore_permissions=True)
		frappe.set_user("Administrator")

	def test_normalize_chat_answer_strips_markdown(self):
		text = prai_openai._normalize_chat_answer("**Title**\n\n1. **Step** — Do this.")
		self.assertNotIn("**", text)
		self.assertIn("Step — Do this.", text)

	def test_parse_model_reply_strips_escalate_marker(self):
		content, suggest = prai_openai._parse_model_reply("Hello world.\nESCALATE: no")
		self.assertEqual(content, "Hello world.")
		self.assertFalse(suggest)

	def test_openai_not_used_when_faq_matches(self):
		from printechs_support.printechs_support_system.api import prai_api

		with patch(
			"printechs_support.printechs_support_system.api.prai_openai.ask_openai_safe",
			return_value=(("should not be used", [], False), "unexpected"),
		):
			result = prai_api.prai_ask("barcode scanner not working on pos")
			self.assertIn("scanner", (result.get("message") or {}).get("content", "").lower())
			self.assertNotEqual((result.get("message") or {}).get("source_type"), "OpenAI")

	def test_openai_used_when_chat_enabled(self):
		from printechs_support.printechs_support_system.api import prai_api, prai_openai

		session = frappe.get_doc({"doctype": "PRAI Chat Session", "user": "Administrator", "messages": []})
		with patch.object(prai_openai, "is_openai_chat_configured", return_value=True):
			with patch.object(
				prai_openai,
				"ask_openai_safe",
				return_value=(("How to calibrate quantum widgets\n\n1. Check power — Ensure device is on.\nESCALATE: no", [], False), ""),
			):
				content, source_type, _, _, suggest = prai_api._resolve_answer(
					"explain quantum widget calibration on retail shelf",
					session=session,
				)
		self.assertEqual(source_type, "OpenAI")
		self.assertIn("quantum widgets", content.lower())
		self.assertFalse(suggest)

	def test_openai_chat_disabled_keeps_ticket_fallback(self):
		from printechs_support.printechs_support_system.api import prai_api, prai_openai

		session = frappe.get_doc({"doctype": "PRAI Chat Session", "user": "Administrator", "messages": []})
		with patch.object(prai_openai, "is_openai_chat_configured", return_value=False):
			content, source_type, _, _, suggest = prai_api._resolve_answer(
				"explain quantum widget calibration on retail shelf",
				session=session,
			)
		self.assertEqual(source_type, "System")
		self.assertIn("support ticket", content.lower())
		self.assertTrue(suggest)

	def test_openai_disabled_keeps_fallback(self):
		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_openai = 0
		settings.save(ignore_permissions=True)
		from printechs_support.printechs_support_system.api import prai_api

		result = prai_api.prai_ask("quantum widget calibration retail shelf")
		self.assertTrue(result.get("suggest_escalation"))

	def test_call_openai_chat_parses_response(self):
		with patch("printechs_support.printechs_support_system.api.prai_openai.make_post_request") as mock_post:
			mock_post.return_value = {"choices": [{"message": {"content": "Step one.\nESCALATE: yes"}}]}
			raw = prai_openai._call_openai_chat(
				messages=[{"role": "user", "content": "test"}],
				model="gpt-4o-mini",
				api_key="sk-test",
			)
			self.assertIn("Step one.", raw)
