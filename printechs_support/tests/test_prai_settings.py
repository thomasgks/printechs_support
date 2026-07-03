# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPraiSettings(FrappeTestCase):
	def test_prai_mvp_disabled_by_default(self):
		from printechs_support.printechs_support_system.doctype.printechs_support_settings.printechs_support_settings import (
			is_prai_mvp_enabled,
		)

		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 0
		settings.save(ignore_permissions=True)

		self.assertFalse(is_prai_mvp_enabled())

	def test_portal_bootstrap_includes_prai_enabled(self):
		from printechs_support.printechs_support_system.api import portal_api

		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_prai_mvp = 1
		settings.save(ignore_permissions=True)

		frappe.set_user("Administrator")
		try:
			payload = portal_api.get_portal_bootstrap()
			self.assertTrue(payload.get("logged_in"))
			self.assertTrue(payload.get("prai_enabled"))
		finally:
			frappe.set_user("Administrator")
			settings.enable_prai_mvp = 0
			settings.save(ignore_permissions=True)

	def test_openai_config_not_exposed_to_portal(self):
		from printechs_support.printechs_support_system.api import portal_api
		from printechs_support.printechs_support_system.doctype.printechs_support_settings.printechs_support_settings import (
			get_prai_openai_config,
		)

		settings = frappe.get_single("Printechs Support Settings")
		settings.enable_openai = 1
		settings.openai_model = "gpt-4o-mini"
		settings.openai_api_key = "sk-test-secret"
		settings.save(ignore_permissions=True)

		config = get_prai_openai_config()
		self.assertTrue(config["enabled"])
		self.assertEqual(config["model"], "gpt-4o-mini")
		self.assertEqual(config["api_key"], "sk-test-secret")

		frappe.set_user("Administrator")
		try:
			payload = portal_api.get_portal_bootstrap()
			self.assertNotIn("openai_api_key", payload)
			self.assertNotIn("enable_openai", payload)
		finally:
			frappe.set_user("Administrator")
			settings.enable_openai = 0
			settings.openai_model = "gpt-4o-mini"
			settings.openai_api_key = ""
			settings.save(ignore_permissions=True)
