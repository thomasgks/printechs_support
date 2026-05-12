# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""End-to-end portal ticket flow: create → read → comment → status → list (API layer)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.printechs_support_system.api import portal_api
from printechs_support.printechs_support_system.api import ticket_workflow as tw
from printechs_support.tests.test_support_agreement import _get_or_create_test_customer


def _get_or_create_ticket_type():
	"""Support Ticket Type name for portal create tests.

	Prefer an active type **without** ``default_team`` so new tickets stay ``Open`` until a team is set
	(exercises assignment + status promotion in tests).
	"""
	names = frappe.get_all(
		"Support Ticket Type",
		filters={"is_active": 1},
		or_filters=[["default_team", "is", "not set"], ["default_team", "=", ""]],
		pluck="name",
		limit=1,
	)
	if names:
		return names[0]
	name = frappe.db.get_value("Support Ticket Type", {"is_active": 1}, "name")
	if name:
		return name
	doc = frappe.new_doc("Support Ticket Type")
	doc.ticket_type_name = f"Portal Test {frappe.generate_hash(length=6)}"
	doc.division = "Software"
	doc.default_priority = "Medium"
	doc.is_active = 1
	doc.insert()
	return doc.name


def _get_or_create_support_team():
	"""Support Team name for assignment tests."""
	name = frappe.db.get_value("Support Team", {"division": "Software"}, "name")
	if name:
		return name
	doc = frappe.new_doc("Support Team")
	doc.team_name = f"Portal Team {frappe.generate_hash(length=6)}"
	doc.division = "Software"
	doc.insert()
	return doc.name


class TestPortalTicketLifecycle(FrappeTestCase):
	def test_full_cycle_create_fetch_comment_status_list(self):
		"""Mirrors customer/internal portal RPCs used by the React SPA."""
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			subject = f"[Auto-test] Portal lifecycle {tag}"

			created = portal_api.create_portal_ticket(
				subject=subject,
				description="<p>Automated integration test — description body.</p>",
				priority="High",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			self.assertTrue(name)
			initial_st = created["status"]
			self.assertTrue(initial_st)
			self.assertEqual(created["customer"], customer)

			self.assertTrue(frappe.db.exists("Support Ticket", name))
			row = frappe.db.get_value(
				"Support Ticket",
				name,
				["subject", "status", "priority", "customer", "description"],
				as_dict=True,
			)
			self.assertEqual(row.subject, subject)
			self.assertEqual(row.status, initial_st)
			self.assertEqual(row.priority, "High")

			detail = portal_api.get_portal_ticket(name)
			self.assertEqual(detail["name"], name)
			self.assertEqual(detail["status"], initial_st)
			self.assertEqual(detail["customer"], customer)

			probe = portal_api.update_portal_ticket(name)
			self.assertTrue(probe.get("ok"))

			edited_subject = f"{subject} — edited"
			upd = portal_api.update_portal_ticket(
				name,
				subject=edited_subject,
				description="<p>Edited description from portal API test.</p>",
				priority="Medium",
			)
			self.assertTrue(upd.get("ok"))
			self.assertEqual(upd.get("priority"), "Medium")
			row_edit = frappe.db.get_value(
				"Support Ticket",
				name,
				["subject", "priority", "description"],
				as_dict=True,
			)
			self.assertEqual(row_edit.subject, edited_subject)
			self.assertEqual(row_edit.priority, "Medium")

			comments = portal_api.get_portal_ticket_comments(name)
			self.assertEqual(comments, [])

			portal_api.add_portal_ticket_comment(
				name,
				"<p>Automated test reply (customer-visible).</p>",
				0,
			)
			comments_after = portal_api.get_portal_ticket_comments(name)
			self.assertEqual(len(comments_after), 1)
			self.assertEqual(comments_after[0]["comment_type"], "Customer Reply")

			# Portal status updates bypass workflow role checks (see update_portal_ticket_status).
			portal_api.update_portal_ticket_status(name, "In Progress")
			detail2 = portal_api.get_portal_ticket(name)
			self.assertEqual(detail2["status"], "In Progress")

			tickets = portal_api.get_portal_tickets(200)
			names = [t["name"] for t in tickets]
			self.assertIn(name, names)

			customer_filtered = portal_api.get_portal_tickets(200, customer=customer)
			customer_filtered_names = [t["name"] for t in customer_filtered]
			self.assertIn(name, customer_filtered_names)
			self.assertTrue(all(t["customer"] == customer for t in customer_filtered))

			customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
			customer_partial = str(customer_name)[1:12]
			customer_partial_filtered = portal_api.get_portal_tickets(200, customer=customer_partial)
			customer_partial_filtered_names = [t["name"] for t in customer_partial_filtered]
			self.assertIn(name, customer_partial_filtered_names)

			customers_payload = portal_api.get_portal_ticket_customers()
			self.assertIn("customers", customers_payload)
			cust_names = {c["name"] for c in customers_payload["customers"]}
			self.assertIn(customer, cust_names)
		finally:
			frappe.set_user("Administrator")

	def test_assign_team_promotes_open_ticket_to_assigned(self):
		"""Setting Support Team on an Open ticket moves status to Assigned (portal + Doc validate)."""
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			team = _get_or_create_support_team()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[Auto-test] Team assign {tag}",
				description="<p>Team → Assigned status.</p>",
				priority="Medium",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Open")

			out = portal_api.update_portal_ticket_assignment(name, team=team)
			self.assertTrue(out.get("ok"))
			self.assertEqual(frappe.db.get_value("Support Ticket", name, "status"), "Assigned")
			self.assertEqual(
				frappe.db.get_value("Support Ticket", name, "action_required_from"),
				"Technician",
			)
			detail = portal_api.get_portal_ticket(name)
			self.assertEqual(detail["status"], "Assigned")
		finally:
			frappe.set_user("Administrator")

	def test_ticket_comments_merge_linked_task_thread(self):
		"""Ticket conversation API includes linked Support Task comments (chronological merge)."""
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[Auto-test] Merge comments {tag}",
				description="<p>Merged thread test.</p>",
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
					"subject": f"Merged task {tag}",
					"status": "Open",
					"responsible_side": "Printechs",
				}
			)
			task.insert(ignore_permissions=True)

			portal_api.add_portal_ticket_comment(ticket_name, "<p>On ticket only.</p>", 0)
			portal_api.add_portal_task_comment(task.name, "<p>On linked task.</p>", 0)

			merged = portal_api.get_portal_ticket_comments(ticket_name)
			self.assertGreaterEqual(len(merged), 2, msg="Ticket thread + merged task rows")
			task_rows = [r for r in merged if r.get("thread_scope") == "task"]
			self.assertEqual(len(task_rows), 1, msg=merged)
			self.assertEqual(task_rows[0].get("task_name"), task.name)
			self.assertIn("On linked task", task_rows[0].get("content") or "")
			ticket_scope = [r for r in merged if (r.get("thread_scope") or "ticket") == "ticket"]
			self.assertTrue(any("On ticket only" in (r.get("content") or "") for r in ticket_scope))
		finally:
			frappe.set_user("Administrator")

	def test_get_portal_ticket_customers_requires_login(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				portal_api.get_portal_ticket_customers()
		finally:
			frappe.set_user("Administrator")

	def test_add_portal_ticket_comment_with_set_status_internal(self):
		"""Internal users may pass ``set_status`` so the reply and status change happen together."""
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			subject = f"[Auto-test] Portal comment+status {tag}"
			created = portal_api.create_portal_ticket(
				subject=subject,
				description="<p>Status-on-send test.</p>",
				priority="Medium",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			out = portal_api.add_portal_ticket_comment(
				name,
				"<p>Update for the customer.</p>",
				0,
				set_status="Waiting for Customer",
			)
			self.assertTrue(out.get("ok"))
			self.assertEqual(out.get("ticket_status"), "Waiting for Customer")
			self.assertEqual(
				frappe.db.get_value("Support Ticket", name, "status"),
				"Waiting for Customer",
			)
		finally:
			frappe.set_user("Administrator")

	def test_waiting_customer_portal_reply_handoff_dual_internal_and_customer_role(self):
		"""Internal+Customer users were skipped by ``not internal``; they must still hand off to technician."""
		frappe.set_user("Administrator")
		try:
			customer = _get_or_create_test_customer()
			ticket_type = _get_or_create_ticket_type()
			tag = frappe.generate_hash(length=8)
			created = portal_api.create_portal_ticket(
				subject=f"[Auto-test] WFC handoff {tag}",
				description="<p>Dual-role handoff test.</p>",
				priority="Medium",
				customer=customer,
				ticket_type=ticket_type,
			)
			name = created["name"]
			tw.assign_ticket(name, frappe.session.user, note="test assign")
			tw.technician_request_customer_input(name, "Please send the serial number.")

			self.assertEqual(
				frappe.db.get_value("Support Ticket", name, "status"),
				"Waiting for Customer",
			)

			email = f"wfc_dual_{frappe.generate_hash(length=8)}@test.local"
			if not frappe.db.exists("User", {"email": email}):
				u = frappe.new_doc("User")
				u.email = email
				u.first_name = "WFC Dual"
				u.send_welcome_email = 0
				u.append("roles", {"role": "Printechs Support Customer"})
				u.append("roles", {"role": "Printechs Support Engineer"})
				u.insert(ignore_permissions=True)
			else:
				user_doc = frappe.get_doc("User", frappe.db.get_value("User", {"email": email}, "name"))
				for role in ("Printechs Support Customer", "Printechs Support Engineer"):
					if not any(r.role == role for r in user_doc.roles):
						user_doc.append("roles", {"role": role})
				user_doc.save(ignore_permissions=True)

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

			frappe.set_user(user_name)
			out = portal_api.add_portal_ticket_comment(
				name,
				"<p>Serial is SN-12345.</p>",
				0,
			)
			self.assertTrue(out.get("ok"))
			self.assertEqual(out.get("ticket_status"), "Waiting for Technician")
			self.assertEqual(
				frappe.db.get_value("Support Ticket", name, "status"),
				"Waiting for Technician",
			)
		finally:
			frappe.set_user("Administrator")
