# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt


from dateutil.parser import ParserError

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_time, getdate, today

from printechs_support.printechs_support_system.api.agreement_portal import (
	provision_agreement_portal_users,
	send_agreement_active_email,
)


class SupportAgreement(Document):
	def validate(self):
		self._normalize_working_hours_fields()
		self.validate_dates()
		self.validate_unique_coverage_categories()
		self.validate_working_hours_window()
		self.apply_expiry_status()
		self.validate_status_transition()
		self.validate_portal_contacts_primary()

	def after_insert(self):
		self._on_active_lifecycle()

	def on_update(self):
		self._on_active_lifecycle()

	def _on_active_lifecycle(self):
		if self.status != "Active":
			return
		provision_agreement_portal_users(self)
		if self.portal_activation_sent:
			return
		try:
			send_agreement_active_email(self)
			self.db_set("portal_activation_sent", 1, update_modified=False)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Support Agreement activation email")

	def validate_portal_contacts_primary(self):
		rows = [r for r in (self.portal_contacts or []) if r.is_primary]
		if len(rows) > 1:
			frappe.throw(_("Only one portal contact can be marked Primary."))

	def apply_expiry_status(self):
		if not self.valid_to:
			return
		if getdate(self.valid_to) >= getdate(today()):
			return
		if self.status in ("Active", "Signed"):
			self.status = "Expired"

	def validate_status_transition(self):
		if self.is_new():
			if self.status == "Active":
				frappe.throw(_("Save as Draft or Signed first; activate in a later step after signing."))
			return
		prev = frappe.db.get_value("Support Agreement", self.name, "status")
		if not prev or prev == self.status:
			return
		if prev == "Draft" and self.status == "Active":
			frappe.throw(_("Set status to Signed before setting Active."))
		if self.status == "Active" and not (self.portal_contacts or []):
			frappe.throw(_("Add at least one portal contact with email before activating."))

	def _normalize_working_hours_fields(self):
		"""Avoid client/server mismatch: hidden SLA time fields must not stay set when WH SLA is off."""
		if not cint(self.working_hours_only):
			self.work_start_time = None
			self.work_end_time = None
			self.sla_holiday_list = None

	def validate_dates(self):
		if self.valid_from and self.valid_to and getdate(self.valid_from) > getdate(self.valid_to):
			frappe.throw(_("Valid To cannot be before Valid From"))

	def validate_unique_coverage_categories(self):
		seen: set[str] = set()
		for row in self.coverage_detail or []:
			if not row.coverage_type and not (row.service_category or "").strip():
				frappe.throw(_("Each coverage row needs a Coverage Type (or legacy Service Category text)."))
			if row.coverage_type:
				key = row.coverage_type.strip().lower()
			else:
				key = (row.service_category or "").strip().lower()
			if key in seen:
				frappe.throw(_("Duplicate coverage line: {0}").format(row.coverage_type or row.service_category))
			seen.add(key)
			if row.coverage_type and self.division:
				row_div = frappe.db.get_value("Coverage Type", row.coverage_type, "division")
				if row_div and row_div != self.division:
					frappe.throw(
						_("Coverage Type {0} is for division {1}; this agreement is {2}.").format(
							row.coverage_type, row_div, self.division
						)
					)
			if row.coverage_type and not (row.service_category or "").strip():
				row.service_category = frappe.db.get_value("Coverage Type", row.coverage_type, "title") or ""

	def validate_working_hours_window(self):
		if not cint(self.working_hours_only):
			return
		if not (self.work_start_time and self.work_end_time):
			return
		try:
			ws = get_time(self.work_start_time)
			we = get_time(self.work_end_time)
		except (ParserError, TypeError, ValueError):
			frappe.throw(_("Work Start and Work End must be valid times when Working Hours Only is enabled."))
		if ws is None or we is None:
			return
		if we <= ws:
			frappe.throw(_("Work End must be after Work Start when Working Hours Only is enabled."))
