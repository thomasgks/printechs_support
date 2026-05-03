# Copyright (c) 2026, Printechs Support and contributors
# License: MIT. See license.txt

"""Structured workflow transitions (desk API)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.printechs_support_system.api import portal_api
from printechs_support.printechs_support_system.api import ticket_workflow as tw
from printechs_support.tests.test_portal_ticket_lifecycle import _get_or_create_ticket_type
from printechs_support.tests.test_support_agreement import _get_or_create_test_customer


class TestSmartTicketWorkflow(FrappeTestCase):
	def test_resolution_and_confirm_desk(self):
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[WF-test] Path {tag}",
				description="<p>Workflow integration.</p>",
				priority="Medium",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Open")

			tw.assign_ticket(name, frappe.session.user, note="Assigned for test")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Assigned")

			tw.technician_send_acknowledgement(name, "Ok we will attend shortly.")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Assigned")

			tw.technician_request_customer_input(name, "Please send logs.")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Waiting for Customer")

			cu = _portal_customer_user(customer)
			if cu:
				frappe.set_user(cu)
				tw.customer_informational_reply(name, "Ok let me double check.")
				self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Waiting for Customer")
				tw.customer_provide_requested_information(name, "Logs attached.")
				frappe.set_user("Administrator")
				self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Waiting for Technician")
			else:
				frappe.db.set_value(
					"Support Ticket",
					name,
					{
						"status": "Waiting for Technician",
						"action_required_from": "Technician",
						"current_owner_type": "Technician",
					},
				)

			tw.technician_send_work_update(name, "Thanks, checking logs now.")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "In Progress")

			tw.technician_send_resolution(name, "Fixed in release x.")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Resolved")

			tw.customer_confirm_resolved(name, "Works now, thanks.")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Closed")
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "action_required_from"), "None")

			log_count = frappe.db.count("Support Ticket Workflow Log", {"parent": name})
			self.assertGreaterEqual(log_count, 6)
		finally:
			frappe.set_user("Administrator")


def _portal_customer_user(customer: str) -> str | None:
	rows = frappe.get_all(
		"User Permission",
		filters={"allow": "Customer", "for_value": customer},
		pluck="user",
	)
	for u in rows:
		if u and "Printechs Support Customer" in frappe.get_roles(u):
			return u
	return None
