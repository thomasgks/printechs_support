# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

_TEST_GROUP = "_Printechs Test Support Agreement Customer Group"
_TEST_TERRITORY = "_Printechs Test Support Agreement Territory"


def _ensure_customer_group(name: str):
	if not frappe.db.exists("Customer Group", {"customer_group_name": name}):
		frappe.get_doc({"doctype": "Customer Group", "customer_group_name": name}).insert(
			ignore_permissions=True
		)
	return name


def _ensure_territory(name: str):
	if not frappe.db.exists("Territory", {"territory_name": name}):
		frappe.get_doc({"doctype": "Territory", "territory_name": name}).insert(ignore_permissions=True)
	return name


def _get_or_create_test_customer():
	_ensure_customer_group(_TEST_GROUP)
	_ensure_territory(_TEST_TERRITORY)
	customer_name = "_Printechs Test Support Agreement Customer"
	if frappe.db.exists("Customer", {"customer_name": customer_name}):
		return frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_group": _TEST_GROUP,
			"territory": _TEST_TERRITORY,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


class TestSupportAgreement(FrappeTestCase):
	def test_normalize_clears_working_hours_fields_when_disabled(self):
		customer = _get_or_create_test_customer()
		doc = frappe.get_doc(
			{
				"doctype": "Support Agreement",
				"customer": customer,
				"division": "Software",
				"agreement_type": "AMC",
				"status": "Draft",
				"working_hours_only": 0,
				"work_start_time": "09:00:00",
				"work_end_time": "18:00:00",
				"sla_holiday_list": None,
			}
		)
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertIsNone(doc.work_start_time)
		self.assertIsNone(doc.work_end_time)

	def test_working_hours_window_valid_when_enabled(self):
		customer = _get_or_create_test_customer()
		doc = frappe.get_doc(
			{
				"doctype": "Support Agreement",
				"customer": customer,
				"division": "Software",
				"agreement_type": "AMC",
				"status": "Draft",
				"working_hours_only": 1,
				"work_start_time": "09:00:00",
				"work_end_time": "18:00:00",
			}
		)
		doc.insert(ignore_permissions=True)

	def test_duplicate_coverage_category_fails(self):
		customer = _get_or_create_test_customer()
		doc = frappe.get_doc(
			{
				"doctype": "Support Agreement",
				"customer": customer,
				"division": "Software",
				"agreement_type": "AMC",
				"status": "Draft",
				"coverage_detail": [
					{"service_category": "Bug Fix", "is_covered": 1},
					{"service_category": "bug fix", "is_covered": 1},
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_valid_dates(self):
		customer = _get_or_create_test_customer()
		doc = frappe.get_doc(
			{
				"doctype": "Support Agreement",
				"customer": customer,
				"division": "Software",
				"agreement_type": "AMC",
				"status": "Draft",
				"valid_from": "2026-01-10",
				"valid_to": "2026-01-01",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_cannot_activate_on_first_save(self):
		customer = _get_or_create_test_customer()
		doc = frappe.get_doc(
			{
				"doctype": "Support Agreement",
				"customer": customer,
				"division": "Software",
				"agreement_type": "AMC",
				"status": "Active",
				"portal_contacts": [{"full_name": "Test", "email": "test_portal_agreement@example.com"}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_draft_to_active_requires_signed(self):
		customer = _get_or_create_test_customer()
		doc = frappe.get_doc(
			{
				"doctype": "Support Agreement",
				"customer": customer,
				"division": "Software",
				"agreement_type": "AMC",
				"status": "Draft",
				"valid_from": "2026-06-01",
				"valid_to": "2027-06-01",
			}
		)
		doc.insert(ignore_permissions=True)
		doc.status = "Active"
		doc.append(
			"portal_contacts",
			{"full_name": "Test User", "email": "test_portal_agreement2@example.com"},
		)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
