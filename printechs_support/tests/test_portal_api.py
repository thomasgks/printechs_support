# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Regression tests for portal RPC methods (same resolution path as Frappe HTTP handler)."""

import frappe
from frappe.tests.utils import FrappeTestCase

PORTAL_MODULE = "printechs_support.printechs_support_system.api.portal_api"

# Methods the SPA calls via /api/method/... — must exist on the module for frappe.get_attr(cmd).
_PORTAL_RPC_METHODS = (
	"get_portal_csrf_token",
	"portal_web_logout",
	"portal_logout",
	"get_portal_bootstrap",
	"get_portal_tickets",
	"get_portal_tasks",
	"get_portal_tasks_for_ticket",
	"get_portal_dashboard_stats",
	"get_portal_ticket",
	"get_portal_task",
	"get_portal_ticket_comments",
	"get_portal_task_comments",
	"get_portal_ticket_desk_history",
	"add_portal_ticket_comment",
	"add_portal_task_comment",
	"update_portal_ticket",
	"update_portal_task",
	"update_portal_ticket_status",
	"update_portal_task_status",
	"update_portal_task_due_date",
	"update_portal_ticket_due_date",
	"get_portal_ticket_files",
	"get_portal_task_files",
	"portal_upload_ticket_file",
	"portal_upload_task_file",
	"get_portal_ticket_status_options",
	"get_portal_task_status_options",
	"get_portal_ticket_customers",
	"get_portal_ticket_types",
	"get_portal_teams",
	"get_portal_assignment_users",
	"create_portal_ticket",
	"create_portal_support_task",
	"update_portal_ticket_assignment",
	"update_portal_task_assignment",
	"mark_ticket_awaiting_customer_resolution",
)


class TestPortalApi(FrappeTestCase):
	def test_rpc_methods_resolve_via_get_attr(self):
		"""Mirrors frappe.handler.get_attr — fails if a whitelisted name is missing from the module."""
		for name in _PORTAL_RPC_METHODS:
			cmd = f"{PORTAL_MODULE}.{name}"
			fn = frappe.get_attr(cmd)
			self.assertTrue(callable(fn), msg=f"{cmd} is not callable")

	def test_status_options_internal_user(self):
		frappe.set_user("Administrator")
		try:
			from printechs_support.printechs_support_system.api import portal_api

			t = portal_api.get_portal_ticket_status_options()
			self.assertIn("options", t)
			self.assertIsInstance(t["options"], list)
			self.assertIn("Open", t["options"])
			self.assertIn("Hold", t["options"])

			u = portal_api.get_portal_task_status_options()
			self.assertIn("options", u)
			self.assertIsInstance(u["options"], list)
			self.assertIn("Open", u["options"])
		finally:
			frappe.set_user("Administrator")

	def test_status_options_reject_guest(self):
		frappe.set_user("Guest")
		try:
			from printechs_support.printechs_support_system.api import portal_api

			with self.assertRaises(frappe.PermissionError):
				portal_api.get_portal_ticket_status_options()
			with self.assertRaises(frappe.PermissionError):
				portal_api.get_portal_task_status_options()
		finally:
			frappe.set_user("Administrator")

	def test_dashboard_stats_reject_guest(self):
		frappe.set_user("Guest")
		try:
			from printechs_support.printechs_support_system.api import portal_api

			with self.assertRaises(frappe.PermissionError):
				portal_api.get_portal_dashboard_stats()
		finally:
			frappe.set_user("Administrator")
