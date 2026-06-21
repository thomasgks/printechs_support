# Copyright (c) 2026, Printechs and contributors

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.printechs_support_system.api import portal_api
from printechs_support.printechs_support_system.api.ticket_comment_emails import notify_task_comment
from printechs_support.tests.test_portal_ticket_lifecycle import _get_or_create_ticket_type
from printechs_support.tests.test_support_agreement import _get_or_create_test_customer


class TestTaskCommentEmails(FrappeTestCase):
	def _make_ticket_task(self, tag: str):
		customer = _get_or_create_test_customer()
		ticket_type = _get_or_create_ticket_type()
		created = portal_api.create_portal_ticket(
			subject=f"[Auto-test] Task email {tag}",
			description="<p>Task email test.</p>",
			priority="Medium",
			customer=customer,
			ticket_type=ticket_type,
		)
		task = frappe.get_doc(
			{
				"doctype": "Support Task",
				"naming_series": "SUP-TSK-.YYYY.-.#####",
				"support_ticket": created["name"],
				"subject": f"Email task {tag}",
				"status": "Open",
				"responsible_side": "Printechs",
				"assigned_to_user": "Administrator",
			}
		)
		task.insert(ignore_permissions=True)
		return created["name"], task.name

	@patch("printechs_support.printechs_support_system.api.ticket_comment_emails._send_bulk")
	def test_internal_task_note_emails_team_not_customer(self, send_bulk):
		tag = frappe.generate_hash(length=8)
		_ticket, task_name = self._make_ticket_task(tag)
		prev_in_test = getattr(frappe.flags, "in_test", False)
		frappe.flags.in_test = False
		frappe.set_user("Administrator")
		try:
			notify_task_comment(
				task_name,
				comment_type="Internal Note",
				comment_by="Administrator",
				content_html="<p>Internal planning only.</p>",
				is_internal_note=True,
				author_is_internal=True,
			)
		finally:
			frappe.flags.in_test = prev_in_test
			frappe.set_user("Administrator")

		self.assertTrue(send_bulk.called, msg="Internal task note should email team")
		self.assertEqual(send_bulk.call_args.kwargs.get("reference_doctype"), "Support Task")
		self.assertIn("Internal note on task", send_bulk.call_args[0][1])

	@patch(
		"printechs_support.printechs_support_system.api.ticket_comment_emails.notify_task_comment"
	)
	def test_portal_task_comment_customer_reply_triggers_notify(self, notify):
		tag = frappe.generate_hash(length=8)
		ticket_name, task_name = self._make_ticket_task(tag)
		frappe.set_user("Administrator")
		try:
			portal_api.add_portal_task_comment(task_name, "<p>Visible update for customer.</p>", 0)
		finally:
			frappe.set_user("Administrator")

		notify.assert_called_once()
		kwargs = notify.call_args.kwargs
		self.assertFalse(kwargs["is_internal_note"])
		self.assertTrue(kwargs["author_is_internal"])

	@patch(
		"printechs_support.printechs_support_system.api.ticket_comment_emails.notify_task_comment"
	)
	def test_portal_task_internal_note_triggers_notify(self, notify):
		tag = frappe.generate_hash(length=8)
		_ticket, task_name = self._make_ticket_task(tag)
		frappe.set_user("Administrator")
		try:
			portal_api.add_portal_task_comment(
				task_name,
				"<p>Team-only coordination.</p>",
				1,
			)
		finally:
			frappe.set_user("Administrator")

		notify.assert_called_once()
		kwargs = notify.call_args.kwargs
		self.assertTrue(kwargs["is_internal_note"])
		self.assertTrue(kwargs["author_is_internal"])

	def test_internal_task_comments_hidden_from_customer_api(self):
		tag = frappe.generate_hash(length=8)
		customer = _get_or_create_test_customer()
		_ticket, task_name = self._make_ticket_task(tag)
		email = f"task_cust_{tag}@test.local"
		if not frappe.db.exists("User", {"email": email}):
			u = frappe.new_doc("User")
			u.email = email
			u.first_name = "Task Customer"
			u.send_welcome_email = 0
			u.append("roles", {"role": "Printechs Support Customer"})
			u.insert(ignore_permissions=True)
		user_name = frappe.db.get_value("User", {"email": email}, "name")
		if not frappe.db.exists(
			"User Permission",
			{"user": user_name, "allow": "Customer", "for_value": customer},
		):
			up = frappe.new_doc("User Permission")
			up.user = user_name
			up.allow = "Customer"
			up.for_value = customer
			up.insert(ignore_permissions=True)

		frappe.set_user("Administrator")
		try:
			portal_api.add_portal_task_comment(task_name, "<p>Customer can see this.</p>", 0)
			portal_api.add_portal_task_comment(task_name, "<p>Internal only.</p>", 1)
		finally:
			frappe.set_user(user_name)
		try:
			rows = portal_api.get_portal_task_comments(task_name)
			contents = [r.get("content") or "" for r in rows]
			self.assertTrue(any("Customer can see" in c for c in contents))
			self.assertFalse(any("Internal only" in c for c in contents))
		finally:
			frappe.set_user("Administrator")
