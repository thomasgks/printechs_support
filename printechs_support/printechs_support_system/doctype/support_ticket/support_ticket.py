# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from printechs_support.assignee_sync import sync_user_assignee_rows
from printechs_support.permissions import get_allowed_customers, user_sees_all_support_records
from printechs_support.printechs_support_system.api.ticket_comment_emails import notify_ticket_comment
from printechs_support.printechs_support_system.api.support import (
	apply_sla_to_ticket,
	apply_ticket_metrics,
	auto_link_support_agreement,
	get_initial_support_ticket_status,
	inherit_from_agreement,
	resolve_customer_from_email,
)
from printechs_support.printechs_support_system.api.ticket_workflow import (
	derive_workflow_routing_for_status,
	sync_waiting_side_fields,
	validate_workflow_consistency,
)

_DIVISION_TICKET_SERIES = {
	"Software": "SOF-TKT-.YYYY.-.#####",
	"Industrial": "IND-TKT-.YYYY.-.#####",
	"Retail": "RET-TKT-.YYYY.-.#####",
}


class SupportTicket(Document):
	def after_insert(self):
		"""Notify customer mobile when staff opens a ticket on their behalf; notify technicians (email + push) on every new customer ticket."""
		if getattr(frappe.flags, "in_test", False):
			return
		if (self.work_scope or "") != "Customer":
			return
		user = frappe.session.user
		if (
			user
			and user != "Guest"
			and user_sees_all_support_records(user)
		):
			try:
				from printechs_support.printechs_support_system.api.mobile_push import (
					notify_customer_new_ticket_mobile,
				)

				notify_customer_new_ticket_mobile(self.name)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Support Ticket mobile push (new ticket)")

		if not self.flags.get("skip_technician_new_ticket_notification"):
			try:
				from printechs_support.printechs_support_system.api.technician_new_ticket_alerts import (
					notify_technicians_new_customer_ticket,
				)

				notify_technicians_new_customer_ticket(self.name)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Support Ticket technician alert (new ticket)")

	def validate(self):
		self._apply_work_scope_defaults()
		self._sync_coverage_type()
		self.validate_customer_scope()
		self.validate_coverage_division()
		self.validate_support_agreement_customer()
		self.validate_portal_customer_status_change()
		auto_link_support_agreement(self)
		inherit_from_agreement(self)
		self._promote_open_to_assigned_when_team_set()
		self._sync_hold_routing()
		apply_sla_to_ticket(self)
		sync_waiting_side_fields(self)
		if not getattr(self.flags, "workflow_transition", False):
			validate_workflow_consistency(self)
		apply_ticket_metrics(self)
		self.sync_ticket_assignees()
		self._append_due_date_conversation_if_due_changed()

	def validate_workflow(self):
		"""Do not run Frappe's *Workflow* DocType checks on this doctype.

		Support Ticket status is owned by :mod:`printechs_support.printechs_support_system.api.ticket_workflow`
		and :func:`validate_workflow_consistency` in :meth:`validate`. If a legacy *Workflow* is still
		``is_active`` (or was only partially removed), core ``validate_workflow`` throws when
		``status`` is not one of that document's *Workflow State* rows—e.g. *Waiting for Technician*—or
		on the second save after a valid smart-workflow transition. The patch
		``deactivate_support_ticket_frappe_workflow`` should keep the Frappe Workflow off; this
		override makes saves safe either way.
		"""
		return

	def on_update(self):
		"""Email customer / team when new thread rows are appended (portal, Desk, or import).

		Portal ``add_portal_ticket_comment`` sets ``skip_comment_notification_hook`` because
		Frappe often does not expose new child-table rows in ``get_doc_before_save()``, so
		len(comments) would not increase here — notifications are invoked explicitly after save.
		"""
		prev = self.get_doc_before_save()
		if not self.flags.get("skip_comment_notification_hook") and prev:
			old_rows = prev.comments or []
			new_rows = self.comments or []
			if len(new_rows) > len(old_rows):
				for row in new_rows[len(old_rows) :]:
					# Due-date audit lines: show in thread; do not email (noise; Version still records).
					if (row.comment_type or "") == "System Update" and row.content and (
						'data-printechs-audit="due-date"' in row.content
					):
						continue
					visible = int(row.is_customer_visible or 0)
					is_internal_note = not bool(visible)
					by = row.comment_by or frappe.session.user
					notify_ticket_comment(
						self.name,
						comment_type=row.comment_type or "Comment",
						comment_by=by,
						content_html=row.content or "",
						is_internal_note=is_internal_note,
						author_is_internal=user_sees_all_support_records(by),
					)

		# Ticket due date → all tasks (manager / Desk). SQL only; does not recurse into task hooks.
		if not self.flags.get("skip_due_sync") and prev:
			if (prev.due_date or None) != (self.due_date or None):
				from printechs_support.due_date_sync import propagate_support_ticket_due_to_tasks

				propagate_support_ticket_due_to_tasks(self.name, self.due_date)

	def sync_ticket_assignees(self):
		sync_user_assignee_rows(self, child_field="ticket_assignees", primary_field="assigned_to")

	def _append_due_date_conversation_if_due_changed(self):
		from printechs_support.due_date_conversation_log import append_due_date_change_comment

		prev = self.get_doc_before_save()
		old_due = prev.due_date if prev else None
		new_due = self.due_date
		if (old_due or None) == (new_due or None):
			return
		append_due_date_change_comment(self, old_due, new_due)

	def _promote_open_to_assigned_when_team_set(self):
		"""Open + Support Team → Assigned (same routing as technician assignment)."""
		if getattr(self.flags, "workflow_transition", False):
			return
		if (self.status or "").strip() != "Open":
			return
		if not (self.team or "").strip():
			return
		ar, cot = derive_workflow_routing_for_status("Assigned")
		self.status = "Assigned"
		self.action_required_from = ar
		self.current_owner_type = cot

	def _sync_hold_routing(self):
		"""Allow Desk users to choose Hold directly without manually changing routing fields."""
		if (self.status or "").strip() != "Hold":
			return
		ar, cot = derive_workflow_routing_for_status("Hold")
		self.action_required_from = ar
		self.current_owner_type = cot

	def _apply_work_scope_defaults(self):
		if not self.work_scope:
			self.work_scope = "Customer"
		if self.work_scope == "Internal":
			self.customer = None
			self.support_agreement = None
			if not self.channel or (self.channel or "") == "Portal":
				self.channel = "Internal"

	def _sync_coverage_type(self):
		if self.coverage_type:
			title = frappe.db.get_value("Coverage Type", self.coverage_type, "title")
			if title:
				self.service_category = title

	def validate_customer_scope(self):
		ws = self.work_scope or "Customer"
		if ws == "Customer" and not self.customer:
			frappe.throw(_("Customer is required for customer-facing tickets."), frappe.ValidationError)
		user = frappe.session.user
		# Desk/internal users may also have Printechs Support Customer for portal testing — they must still use Internal scope when chosen.
		if (
			user
			and user != "Guest"
			and not user_sees_all_support_records(user)
			and "Printechs Support Customer" in frappe.get_roles(user)
			and ws != "Customer"
		):
			frappe.throw(_("Portal users can only create customer-facing tickets."), frappe.ValidationError)

	def validate_coverage_division(self):
		if not self.coverage_type or not self.division:
			return
		ct_div = frappe.db.get_value("Coverage Type", self.coverage_type, "division")
		if ct_div and ct_div != self.division:
			frappe.throw(
				_("Coverage Type {0} is for division {1}; this ticket is {2}.").format(
					self.coverage_type, ct_div, self.division
				),
				frappe.ValidationError,
			)

	def before_insert(self):
		self._apply_ticket_type_defaults()
		self._set_division_naming_series()
		if not self.opening_date:
			self.opening_date = now_datetime()
		user = frappe.session.user
		if (
			user != "Guest"
			and "Printechs Support Customer" in frappe.get_roles(user)
			and not user_sees_all_support_records(user)
		):
			self.work_scope = "Customer"
			custs = get_allowed_customers(user)
			if custs and not self.customer:
				self.customer = custs[0]
			if not self.channel or self.channel == "Internal":
				self.channel = "Portal"
			if not self.contact_email:
				self.contact_email = user
		if not self.customer and self.contact_email:
			cust = resolve_customer_from_email(self.contact_email)
			if cust:
				self.customer = cust
			elif self.flags.get("ignore_mandatory"):
				fb = None
				if frappe.db.exists("Printechs Support Settings", "Printechs Support Settings"):
					fb = frappe.db.get_single_value("Printechs Support Settings", "fallback_customer")
				if fb:
					self.customer = fb
				else:
					frappe.throw(
						_(
							"Cannot resolve Customer from this email. Link the sender to a Contact tied to a Customer, "
							"or set Fallback Customer in Printechs Support Settings."
						)
					)
		if self.flags.get("ignore_mandatory") and self.contact_email:
			self.channel = "Email"
			if not self.source_email_id:
				self.source_email_id = self.contact_email
	def _apply_ticket_type_defaults(self):
		if not self.ticket_type:
			return
		tt = frappe.db.get_value(
			"Support Ticket Type",
			self.ticket_type,
			["division", "default_priority", "default_team"],
			as_dict=True,
		)
		if not tt:
			return
		if tt.division:
			self.division = tt.division
		# Portal create passes explicit priority; do not override when flagged.
		if tt.default_priority and not self.flags.get("priority_from_portal"):
			self.priority = tt.default_priority
		if tt.default_team and not self.team:
			self.team = tt.default_team

	def _set_division_naming_series(self):
		division = (self.division or "Software").strip()
		self.naming_series = _DIVISION_TICKET_SERIES.get(division, _DIVISION_TICKET_SERIES["Software"])

	def validate_portal_customer_status_change(self):
		"""Block portal customers from changing status except Resolved during an open confirmation window."""
		if getattr(self.flags, "workflow_transition", False):
			return
		if getattr(self.flags, "ignore_customer_status_guard", False):
			return
		user = frappe.session.user
		if user in ("Guest", "Administrator"):
			return
		if user_sees_all_support_records(user):
			return
		if "Printechs Support Customer" not in frappe.get_roles(user):
			return

		from frappe.utils import get_datetime, now_datetime

		terminal = frozenset({"Resolved", "Closed", "Cancelled"})
		prev = self.get_doc_before_save()

		if self.is_new():
			allowed = get_initial_support_ticket_status()
			if (self.status or "") != allowed:
				frappe.throw(
					_("You cannot set this status when creating a ticket."),
					frappe.ValidationError,
				)
			return

		if not prev or (prev.status or "") == (self.status or ""):
			return

		if (self.status or "") == "Resolved":
			deadline = frappe.db.get_value("Support Ticket", self.name, "customer_resolution_deadline")
			if not deadline:
				frappe.throw(
					_("You can only set Resolved when your support team has opened a confirmation window."),
					frappe.ValidationError,
				)
			if now_datetime() > get_datetime(deadline):
				frappe.throw(_("The confirmation period has ended."), frappe.ValidationError)
			if (prev.status or "") in terminal:
				frappe.throw(_("This ticket is already closed."), frappe.ValidationError)
			return

		frappe.throw(
			_("You cannot change the ticket status from the portal. Please contact your support team."),
			frappe.ValidationError,
		)

	def validate_support_agreement_customer(self):
		if not self.support_agreement or not self.customer:
			return
		ag_customer = frappe.db.get_value("Support Agreement", self.support_agreement, "customer")
		if ag_customer and ag_customer != self.customer:
			self.support_agreement = None

	def get_support_portal_ticket_url(self) -> str:
		"""Absolute URL to this ticket in the website support portal (for Notification email HTML)."""
		from urllib.parse import quote

		from frappe.utils import get_url

		base = get_url().rstrip("/")
		name = (self.name or "").strip()
		if not name:
			return f"{base}/support-portal"
		return f"{base}/support-portal/tickets/{quote(name)}"

	def get_acknowledgement_brand_name(self) -> str:
		try:
			return (
				(frappe.defaults.get_defaults().get("company") or "").strip()
				or frappe.db.get_single_value("Global Defaults", "default_company")
				or frappe.get_system_settings("app_name")
				or "Printechs"
			)
		except Exception:
			return "Printechs"

	def get_acknowledgement_brand_initial(self) -> str:
		s = (self.get_acknowledgement_brand_name() or "P").strip() or "P"
		return s[0].upper()

	def get_acknowledgement_owner_display(self) -> str:
		owner = (self.owner or "").strip() or "Administrator"
		if owner == "Administrator":
			return str(_("Printechs Support"))
		fn = frappe.db.get_value("User", owner, "full_name")
		return (fn or owner).strip()

	def get_acknowledgement_owner_initials(self) -> str:
		label = self.get_acknowledgement_owner_display()
		parts = [p for p in label.replace(".", " ").split() if p]
		if not parts:
			return "?"
		if len(parts) >= 2:
			return (parts[0][0] + parts[-1][0]).upper()
		return (parts[0][:2]).upper()

	def get_acknowledgement_opened_datetime_display(self) -> str:
		from frappe.utils import format_datetime, get_datetime

		raw = self.opening_date or self.creation
		if not raw:
			return ""
		try:
			return format_datetime(get_datetime(raw))
		except Exception:
			return str(raw)

	def get_acknowledgement_description_block_html(self, max_chars: int = 4000) -> str:
		"""HTML fragment (ticket description): label + panel for any email or Jinja (use ``|safe``)."""
		from html import escape as html_escape

		from frappe.utils import strip_html

		label = html_escape(str(_("Description")))
		raw = strip_html(self.description or "").strip()
		if not raw:
			inner = f'<span style="color:#94a3b8;font-style:italic;">{html_escape(str(_("No description provided.")))}</span>'
		else:
			s = html_escape(raw)
			if len(s) > max_chars:
				s = s[: max_chars - 1] + "…"
			inner = s.replace("\n", "<br/>")
		return (
			'<div style="margin:14px 0 16px 0;padding-top:14px;border-top:1px solid #e2e8f0;">'
			'<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">'
			f"{label}</div>"
			'<div style="font-size:14px;color:#334155;line-height:1.55;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;">'
			f"{inner}</div></div>"
		)
