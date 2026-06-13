# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Customer resolution window + auto-resolve past deadline."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from printechs_support.printechs_support_system.api import portal_api
from printechs_support.tasks import (
	auto_close_resolved_support_tickets_past_deadline,
	auto_resolve_support_tickets_past_deadline,
)
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
					"action_required_from": "Customer",
					"assigned_to": "Administrator",
					"due_date": now_datetime(),
					"last_internal_update_on": now_datetime(),
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

	def test_auto_resolve_ignores_deadline_without_confirmation_flag(self):
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[Auto-test] Ignore stale deadline {tag}",
				description="<p>Should stay open.</p>",
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
					"customer_confirmation_required": 0,
					"action_required_from": "Technician",
				},
			)
			auto_resolve_support_tickets_past_deadline()
			row = frappe.db.get_value(
				"Support Ticket",
				name,
				["status", "customer_resolution_deadline", "customer_confirmation_required"],
				as_dict=True,
			)
			self.assertEqual(row.status, "Open")
			self.assertEqual(row.customer_confirmation_required, 0)
		finally:
			frappe.set_user("Administrator")

	def test_auto_close_resolved_past_quiet_period(self):
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[Auto-test] Auto close resolved {tag}",
				description="<p>Auto-close test.</p>",
				priority="Medium",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			frappe.db.set_value(
				"Support Ticket",
				name,
				{
					"status": "Resolved",
					"action_required_from": "Customer",
					"current_owner_type": "Customer",
					"resolved_on": add_to_date(now_datetime(), days=-8),
				},
			)
			auto_close_resolved_support_tickets_past_deadline()
			row = frappe.db.get_value(
				"Support Ticket",
				name,
				["status", "closed_on", "action_required_from"],
				as_dict=True,
			)
			self.assertEqual(row.status, "Closed")
			self.assertIsNotNone(row.closed_on)
			self.assertEqual(row.action_required_from, "None")
		finally:
			frappe.set_user("Administrator")
