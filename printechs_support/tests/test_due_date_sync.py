# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Support Ticket / Support Task due_date stay aligned (Desk + portal)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

from printechs_support.printechs_support_system.api import portal_api
from printechs_support.tests.test_portal_ticket_lifecycle import _get_or_create_ticket_type
from printechs_support.tests.test_support_agreement import _get_or_create_test_customer


def _ticket_and_task():
	frappe.set_user("Administrator")
	customer = _get_or_create_test_customer()
	tt = _get_or_create_ticket_type()
	tag = frappe.generate_hash(length=6)
	created = portal_api.create_portal_ticket(
		subject=f"[Due sync] {tag}",
		description="<p>Sync test.</p>",
		priority="Medium",
		customer=customer,
		ticket_type=tt,
	)
	ticket_name = created["name"]
	task = frappe.get_doc(
		{
			"doctype": "Support Task",
			"naming_series": "SUP-TSK-.YYYY.-.#####",
			"support_ticket": ticket_name,
			"subject": f"Sync task {tag}",
			"status": "Open",
			"responsible_side": "Printechs",
		}
	)
	task.insert(ignore_permissions=True)
	return ticket_name, task.name


class TestDueDateSync(FrappeTestCase):
	def test_task_due_syncs_to_ticket_via_portal_api(self):
		frappe.set_user("Administrator")
		ticket_name, task_name = _ticket_and_task()
		payload = "2030-07-01 16:00:00"
		out = portal_api.update_portal_task_due_date(task_name, payload)
		self.assertTrue(out.get("ok"))
		ticket_due = frappe.db.get_value("Support Ticket", ticket_name, "due_date")
		self.assertIsNotNone(ticket_due)
		self.assertEqual(get_datetime(ticket_due), get_datetime(payload))

	def test_ticket_due_syncs_to_tasks_via_portal_api(self):
		frappe.set_user("Administrator")
		ticket_name, task_name = _ticket_and_task()
		payload = "2030-08-10 11:30:00"
		out = portal_api.update_portal_ticket_due_date(ticket_name, payload)
		self.assertTrue(out.get("ok"))
		task_due = frappe.db.get_value("Support Task", task_name, "due_date")
		self.assertIsNotNone(task_due)
		self.assertEqual(get_datetime(task_due), get_datetime(payload))

	def test_get_portal_ticket_includes_can_edit_ticket_schedule(self):
		frappe.set_user("Administrator")
		ticket_name, _ = _ticket_and_task()
		row = portal_api.get_portal_ticket(ticket_name)
		self.assertIn("can_edit_ticket_schedule", row)
		self.assertIsInstance(row.get("can_edit_ticket_schedule"), bool)

	def test_due_date_calendar_matches_naive_wall_date(self):
		frappe.set_user("Administrator")
		ticket_name, _ = _ticket_and_task()
		portal_api.update_portal_ticket_due_date(ticket_name, "2030-12-15 09:00:00")
		row = portal_api.get_portal_ticket(ticket_name)
		self.assertEqual(row.get("due_date_calendar"), "2030-12-15")
		self.assertIn("2030-12-15", str(row.get("due_date") or ""))
		out = portal_api.update_portal_ticket_due_date(ticket_name, "")
		self.assertIsNone(out.get("due_date_calendar"))

	def test_due_date_change_comment_includes_changed_by(self):
		frappe.set_user("Administrator")
		ticket_name, _ = _ticket_and_task()
		portal_api.update_portal_ticket_due_date(ticket_name, "2030-09-15 10:00:00")
		rows = frappe.get_all(
			"Support Ticket Comment",
			filters={"parent": ticket_name, "parenttype": "Support Ticket"},
			fields=["content", "comment_by"],
			order_by="creation desc",
			limit_page_length=3,
		)
		self.assertTrue(rows)
		latest = next((r for r in rows if "Due date updated" in (r.content or "")), None)
		self.assertIsNotNone(latest, msg="Expected a due-date system comment on the ticket")
		self.assertIn("Changed by", latest.content)
		self.assertEqual(latest.comment_by, "Administrator")
