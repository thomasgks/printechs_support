# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	ensure_user_expo_push_token_field()
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "support_portal_enabled",
					"fieldtype": "Check",
					"label": "Support Portal Enabled",
					"insert_after": "customer_group",
					"default": "0",
				},
				{
					"fieldname": "printechs_allowed_ticket_types",
					"fieldtype": "Table",
					"label": "Portal — Allowed Ticket Types",
					"description": "If empty, all active Support Ticket Types are shown in the portal. If rows exist, only these types are offered.",
					"options": "Customer Allowed Ticket Type",
					"insert_after": "support_portal_enabled",
				},
			],
		}
	)


def sync_printechs_support_workspace():
	"""Re-import Workspace JSON from the app (overrides stale DB on migrate)."""
	from frappe.modules.utils import reload_doc

	reload_doc("printechs_support_system", "Workspace", "Printechs Support", force=True)
	reload_doc("prai_studio", "Workspace", "PRAI Studio", force=True)


def after_migrate():
	ensure_user_expo_push_token_field()
	ensure_customer_allowed_ticket_types_field()
	sync_printechs_support_workspace()
	ensure_printechs_support_settings()
	frappe.get_single("Portal Settings").sync_menu()
	from printechs_support.setup_support_extras import ensure_permissions, ensure_roles

	ensure_roles()
	ensure_permissions()
	from printechs_support.phase_i_finalize import run_phase_i_finalize

	run_phase_i_finalize()


def ensure_user_expo_push_token_field():
	"""Expo device token for Printechs Support mobile push (set via portal_api.register_mobile_push_token)."""
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "printechs_expo_push_token",
					"fieldtype": "Data",
					"label": "Printechs Expo Push Token",
					"description": "Registered by the Printechs Support mobile app for ticket notifications.",
					"insert_after": "mobile_no",
				},
			],
		}
	)


def ensure_customer_allowed_ticket_types_field():
	"""Add portal ticket-type mapping table to Customer (idempotent)."""
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "printechs_allowed_ticket_types",
					"fieldtype": "Table",
					"label": "Portal — Allowed Ticket Types",
					"description": "If empty, all active Support Ticket Types are shown in the portal. If rows exist, only these types are offered.",
					"options": "Customer Allowed Ticket Type",
					"insert_after": "support_portal_enabled",
				},
			],
		}
	)


def ensure_printechs_support_settings():
	if frappe.db.exists("Printechs Support Settings", "Printechs Support Settings"):
		return
	doc = frappe.new_doc("Printechs Support Settings")
	doc.insert(ignore_permissions=True)


def ensure_prai_studio_upload_limits():
	"""Ensure site config allows large PRAI Studio source ZIP uploads (idempotent)."""
	min_bytes = 200 * 1024 * 1024
	current = int(frappe.get_site_config().get("max_file_size") or 0)
	if current >= min_bytes:
		return
	from frappe.installer import update_site_config

	update_site_config("max_file_size", min_bytes)

