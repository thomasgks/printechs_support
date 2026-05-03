# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Portal Support Task due date: API + permission rules (assignee vs customer)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

from printechs_support.permissions import user_can_edit_portal_task_schedule
from printechs_support.printechs_support_system.api import portal_api
from printechs_support.tests.test_portal_ticket_lifecycle import _get_or_create_ticket_type
from printechs_support.tests.test_support_agreement import _get_or_create_test_customer


def _create_ticket_and_task():
	"""Return (ticket_name, task_name). Caller must be Administrator."""
	customer = _get_or_create_test_customer()
	ticket_type = _get_or_create_ticket_type()
	tag = frappe.generate_hash(length=6)
	created = portal_api.create_portal_ticket(
		subject=f"[Test due date] {tag}",
		description="<p>Due date API test.</p>",
		priority="Medium",
		customer=customer,
		ticket_type=ticket_type,
	)
	ticket_name = created["name"]
	task = frappe.get_doc(
		{
			"doctype": "Support Task",
			"naming_series": "SUP-TSK-.YYYY.-.#####",
			"support_ticket": ticket_name,
			"subject": f"Due date integration {tag}",
			"status": "Open",
			"responsible_side": "Printechs",
		}
	)
	task.insert(ignore_permissions=True)
	return ticket_name, task.name


class TestPortalTaskDueDate(FrappeTestCase):
	def test_administrator_can_update_due_date_via_api(self):
		frappe.set_user("Administrator")
		try:
			_ticket, task_name = _create_ticket_and_task()
			self.assertTrue(user_can_edit_portal_task_schedule("Administrator", task_name))

			payload = "2030-06-15 14:30:00"
			out = portal_api.update_portal_task_due_date(task_name, payload)
			self.assertTrue(out.get("ok"))
			self.assertIsNotNone(out.get("due_date"))
			stored = frappe.db.get_value("Support Task", task_name, "due_date")
			self.assertIsNotNone(stored)
			self.assertEqual(get_datetime(stored), get_datetime(payload))

			out_clear = portal_api.update_portal_task_due_date(task_name, "")
			self.assertTrue(out_clear.get("ok"))
			self.assertIsNone(out_clear.get("due_date"))
			self.assertIsNone(frappe.db.get_value("Support Task", task_name, "due_date"))

			detail = portal_api.get_portal_task(task_name)
			self.assertIn("can_edit_task_schedule", detail)
			self.assertTrue(bool(detail.get("can_edit_task_schedule")))
		finally:
			frappe.set_user("Administrator")

	def test_get_portal_task_exposes_can_edit_task_schedule(self):
		frappe.set_user("Administrator")
		try:
			_ticket, task_name = _create_ticket_and_task()
			detail = portal_api.get_portal_task(task_name)
			self.assertTrue("can_edit_task_schedule" in detail)
			self.assertIsInstance(detail.get("can_edit_task_schedule"), bool)
			self.assertTrue(detail["can_edit_task_schedule"])
		finally:
			frappe.set_user("Administrator")

	def test_assignee_without_desk_role_can_edit_schedule(self):
		"""Technician modeled as portal user assigned on the task, no Support Team role."""
		frappe.set_user("Administrator")
		customer = _get_or_create_test_customer()
		_ticket, task_name = _create_ticket_and_task()

		email = f"due_test_{frappe.generate_hash(length=6).lower()}@portal-due.test"
		if frappe.db.exists("User", {"email": email}):
			frappe.delete_doc("User", frappe.db.get_value("User", {"email": email}, "name"), force=1)

		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "DueTest",
				"send_welcome_email": 0,
			}
		)
		u.flags.ignore_permissions = True
		u.insert()

		# Website User + portal customer (same pattern as real portal technicians with customer scope)
		u.add_roles("Printechs Support Customer")
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": u.name,
				"allow": "Customer",
				"for_value": customer,
			}
		).insert(ignore_permissions=True)

		task = frappe.get_doc("Support Task", task_name)
		task.append("task_assignees", {"user": u.name, "is_primary": 1})
		task.save(ignore_permissions=True)

		frappe.set_user(u.name)
		try:
			self.assertFalse(frappe.db.get_value("Has Role", {"parent": u.name, "role": "Support Team"}, "name"))
			self.assertTrue(user_can_edit_portal_task_schedule(u.name, task_name))

			detail = portal_api.get_portal_task(task_name)
			self.assertTrue(
				detail.get("can_edit_task_schedule"),
				msg="get_portal_task must set can_edit_task_schedule for assignees",
			)

			out = portal_api.update_portal_task_due_date(task_name, "2031-01-20 09:00:00")
			self.assertTrue(out.get("ok"))
			stored = frappe.db.get_value("Support Task", task_name, "due_date")
			self.assertIsNotNone(stored)
			self.assertEqual(get_datetime(stored), get_datetime("2031-01-20 09:00:00"))
		finally:
			frappe.set_user("Administrator")

	def test_portal_only_customer_cannot_edit_ticket_or_task_due_date(self):
		"""End customers (not staff, not assignee) may not change due dates even with Write on their ticket."""
		frappe.set_user("Administrator")
		customer = _get_or_create_test_customer()
		ticket_name, task_name = _create_ticket_and_task()

		email = f"cust_only_{frappe.generate_hash(length=6).lower()}@portal-due.test"
		if frappe.db.exists("User", {"email": email}):
			frappe.delete_doc("User", frappe.db.get_value("User", {"email": email}, "name"), force=1)

		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "CustOnly",
				"send_welcome_email": 0,
			}
		)
		u.flags.ignore_permissions = True
		u.insert()
		u.add_roles("Printechs Support Customer")
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": u.name,
				"allow": "Customer",
				"for_value": customer,
			}
		).insert(ignore_permissions=True)

		frappe.set_user(u.name)
		try:
			self.assertFalse(user_can_edit_portal_task_schedule(u.name, task_name))

			with self.assertRaises(frappe.PermissionError):
				portal_api.update_portal_ticket_due_date(ticket_name, "2032-06-01 12:00:00")
			with self.assertRaises(frappe.PermissionError):
				portal_api.update_portal_task_due_date(task_name, "2032-06-02 14:00:00")

			ticket_row = portal_api.get_portal_ticket(ticket_name)
			self.assertFalse(bool(ticket_row.get("can_edit_ticket_schedule")))
			task_detail = portal_api.get_portal_task(task_name)
			self.assertFalse(bool(task_detail.get("can_edit_task_schedule")))
		finally:
			frappe.set_user("Administrator")
