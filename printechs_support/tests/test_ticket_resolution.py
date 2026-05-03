# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Customer resolution window + auto-resolve past deadline."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from printechs_support.printechs_support_system.api import portal_api
from printechs_support.tasks import auto_resolve_support_tickets_past_deadline
from printechs_support.tests.test_portal_ticket_lifecycle import _get_or_create_ticket_type
from printechs_support.tests.test_support_agreement import _get_or_create_test_customer


class TestTicketResolution(FrappeTestCase):
	def test_auto_resolve_past_deadline(self):
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[Auto-test] Resolution deadline {tag}",
				description="<p>Auto-resolve test.</p>",
				priority="Medium",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			past = add_to_date(now_datetime(), hours=-1)
			frappe.db.set_value(
				"Support Ticket",
				name,
				{
					"customer_resolution_deadline": past,
					"customer_confirmation_required": 1,
				},
			)
			auto_resolve_support_tickets_past_deadline()
			row = frappe.db.get_value(
				"Support Ticket",
				name,
				["status", "customer_resolution_deadline", "customer_confirmation_required"],
				as_dict=True,
			)
			self.assertEqual(row.status, "Resolved")
			self.assertIsNone(row.customer_resolution_deadline)
			self.assertEqual(row.customer_confirmation_required, 0)
		finally:
			frappe.set_user("Administrator")
