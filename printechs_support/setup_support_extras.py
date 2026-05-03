# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Create roles, permissions, workflows, and acknowledgement notification (idempotent)."""

import textwrap

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

ROLES = [
	{"role_name": "Printechs Support Customer", "desk_access": 0},
	{"role_name": "Printechs Support Coordinator", "desk_access": 1},
	{"role_name": "Printechs Support Engineer", "desk_access": 1},
	{"role_name": "Printechs Support Project Manager", "desk_access": 1},
]

WORKFLOW_ROLE = "Support Team"
ALLOW_EDIT_ROLE = "Support Team"

# Bumped when the customer acknowledgement email layout changes (existing Notification rows are updated).
SUPPORT_TICKET_ACK_EMAIL_VERSION = "printechs-ack-email-v3"


def _support_ticket_acknowledgement_message() -> str:
	"""HTML body for Notification ``Support Ticket Acknowledgement`` (Jinja: ``doc`` = Support Ticket)."""
	return (
		f"<!-- {SUPPORT_TICKET_ACK_EMAIL_VERSION} -->\n"
		+ textwrap.dedent(
			"""
			<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0;padding:24px 12px;background:#f1f5f9;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
			  <tr>
			    <td align="center">
			      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 10px 40px -18px rgba(15,23,42,0.2);">
			        <tr>
			          <td style="padding:22px 26px 8px 26px;">
			            <table role="presentation" width="100%"><tr>
			              <td width="48" valign="top">
			                <div style="width:42px;height:42px;background:#1d4ed8;border-radius:8px;line-height:42px;text-align:center;color:#ffffff;font-weight:700;font-size:18px;">{{ doc.get_acknowledgement_brand_initial() }}</div>
			              </td>
			              <td valign="middle" style="padding-left:8px;">
			                <div style="font-size:22px;font-weight:700;color:#0f172a;letter-spacing:-0.02em;">Your request was received</div>
			                <div style="margin-top:4px;font-size:13px;color:#64748b;">{{ doc.get_acknowledgement_brand_name() }} &middot; Support</div>
			              </td>
			            </tr></table>
			          </td>
			        </tr>
			        <tr>
			          <td style="padding:8px 26px 22px 26px;font-size:15px;line-height:1.55;color:#334155;">
			            <p style="margin:0 0 14px 0;">Your request regarding
			              <a href="{{ doc.get_support_portal_ticket_url() }}" style="color:#1d4ed8;font-weight:600;text-decoration:none;">{{ doc.subject }}</a>
			              <span style="color:#64748b;font-weight:600;">(#{{ doc.name }})</span>
			              was received. You will be notified of updates in the portal.</p>
			            {{ doc.get_acknowledgement_description_block_html()|safe }}
			            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:18px 0 8px 0;">
			              <tr>
			                <td bgcolor="#1d4ed8" style="border-radius:8px;">
			                  <a href="{{ doc.get_support_portal_ticket_url() }}" style="display:inline-block;padding:12px 28px;font-size:14px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.04em;">VIEW IN PORTAL</a>
			                </td>
			              </tr>
			            </table>
			            <p style="margin:16px 0 0 0;font-size:12px;color:#94a3b8;">Customer: <strong style="color:#475569;">{{ doc.customer_name or doc.customer or '—' }}</strong></p>
			          </td>
			        </tr>
			        <tr>
			          <td style="border-top:1px solid #e2e8f0;padding:18px 26px 22px 26px;background:#f8fafc;">
			            <table role="presentation" width="100%"><tr>
			              <td width="44" valign="top">
			                <div style="width:40px;height:40px;border-radius:8px;background:#0d9488;line-height:40px;text-align:center;color:#ffffff;font-weight:700;font-size:13px;">{{ doc.get_acknowledgement_owner_initials() }}</div>
			              </td>
			              <td valign="top" style="padding-left:10px;font-size:13px;color:#475569;line-height:1.45;">
			                <strong style="color:#0f172a;">{{ doc.get_acknowledgement_owner_display() }}</strong><br/>
			                <span style="color:#64748b;">Submitted &middot; {{ doc.get_acknowledgement_opened_datetime_display() }}</span>
			              </td>
			            </tr></table>
			            <p style="margin:16px 0 0 0;font-size:12px;color:#64748b;line-height:1.5;">Support portal link:<br/>
			              <a href="{{ doc.get_support_portal_ticket_url() }}" style="color:#1d4ed8;word-break:break-all;">{{ doc.get_support_portal_ticket_url() }}</a>
			            </p>
			          </td>
			        </tr>
			      </table>
			      <p style="margin:16px 0 0 0;font-size:11px;color:#94a3b8;max-width:560px;">You can reply to this email when your mailbox is linked to the ticket thread.</p>
			    </td>
			  </tr>
			</table>
			"""
		).strip()
	)


def ensure_roles():
	for r in ROLES:
		if frappe.db.exists("Role", r["role_name"]):
			continue
		frappe.get_doc({"doctype": "Role", **r}).insert(ignore_permissions=True)


def ensure_workflow_state(name: str) -> None:
	if frappe.db.exists("Workflow State", name):
		return
	frappe.get_doc(
		{"doctype": "Workflow State", "workflow_state_name": name, "style": "Primary"}
	).insert(ignore_permissions=True)


def ensure_workflow_action(name: str) -> None:
	if frappe.db.exists("Workflow Action Master", name):
		return
	frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": name}).insert(
		ignore_permissions=True
	)


def add_custom_docperm(doctype: str, role: str, if_owner: int = 0, **perms: int) -> None:
	if frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "if_owner": if_owner},
		"name",
	):
		return
	row = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			"if_owner": if_owner,
			**perms,
		}
	)
	row.insert(ignore_permissions=True)
	validate_permissions_for_doctype(doctype)


def ensure_permissions():
	masters_read = [
		"Support Ticket Type",
		"Support Team",
		"Support SLA Template",
		"Delay Reason",
		"Printechs Support Settings",
	]
	transactions = ["Support Agreement", "Support Ticket", "Support Task"]

	coordinator = "Printechs Support Coordinator"
	engineer = "Printechs Support Engineer"
	pm = "Printechs Support Project Manager"
	customer = "Printechs Support Customer"
	# When any Custom DocPerm exists for a DocType, Frappe uses *only* Custom DocPerm and
	# ignores standard DocType permissions. Without these rows, System Manager / Support Team
	# lose read access and list views return no rows (even though records exist in the DB).
	baseline_desk_roles = ("System Manager", "Support Team")

	for dt in masters_read:
		for role in (coordinator, engineer, pm):
			add_custom_docperm(
				dt,
				role,
				0,
				read=1,
				write=1,
				create=1,
				delete=0,
				email=1,
				export=1,
				print=1,
				report=1,
				share=1,
			)
		for role in baseline_desk_roles:
			add_custom_docperm(
				dt,
				role,
				0,
				read=1,
				write=1,
				create=1,
				delete=0,
				email=1,
				export=1,
				print=1,
				report=1,
				share=1,
			)

	for dt in transactions:
		add_custom_docperm(
			dt,
			coordinator,
			0,
			read=1,
			write=1,
			create=1,
			delete=1,
			email=1,
			export=1,
			print=1,
			report=1,
			share=1,
		)
		add_custom_docperm(
			dt,
			engineer,
			0,
			read=1,
			write=1,
			create=1,
			delete=0,
			email=1,
			export=1,
			print=1,
			report=1,
			share=1,
		)
		add_custom_docperm(
			dt,
			pm,
			0,
			read=1,
			write=1,
			create=1,
			delete=0,
			email=1,
			export=1,
			print=1,
			report=1,
			share=1,
		)
		for role in baseline_desk_roles:
			add_custom_docperm(
				dt,
				role,
				0,
				read=1,
				write=1,
				create=1,
				delete=1,
				email=1,
				export=1,
				print=1,
				report=1,
				share=1,
			)

	add_custom_docperm(
		"Support Ticket",
		customer,
		0,
		read=1,
		write=1,
		create=1,
		delete=0,
		email=0,
		export=0,
		print=1,
		report=0,
		share=0,
	)
	add_custom_docperm(
		"Support Task",
		customer,
		0,
		read=1,
		write=0,
		create=0,
		delete=0,
		email=0,
		export=0,
		print=0,
		report=0,
		share=0,
	)


def build_support_ticket_workflow():
	"""Deprecated: do not attach a Frappe ``Workflow`` to Support Ticket.

	Status transitions are handled by ``ticket_workflow`` (Python APIs + validations). Enabling both
	systems causes Desk errors such as \"Workflow State transition not allowed from Draft to Open\".
	Use ``ticket_workflow`` RPCs / workflow_log instead.
	"""
	return


def build_support_task_workflow():
	if frappe.db.exists("Workflow", {"workflow_name": "Support Task Workflow"}):
		return

	task_states = [
		"Open",
		"In Progress",
		"Waiting for Customer",
		"Waiting for Printechs",
		"Completed",
		"Cancelled",
		"Delayed",
	]
	for s in task_states:
		ensure_workflow_state(s)

	for a in ("Start", "Hand to Customer", "Hand to Printechs", "Complete", "Cancel Task"):
		ensure_workflow_action(a)

	transitions = [
		("Open", "Start", "In Progress"),
		("Open", "Cancel Task", "Cancelled"),
		("In Progress", "Hand to Customer", "Waiting for Customer"),
		("In Progress", "Hand to Printechs", "Waiting for Printechs"),
		("In Progress", "Complete", "Completed"),
		("Waiting for Customer", "Start", "In Progress"),
		("Waiting for Printechs", "Start", "In Progress"),
		("Delayed", "Start", "In Progress"),
	]

	wf = frappe.new_doc("Workflow")
	wf.workflow_name = "Support Task Workflow"
	wf.document_type = "Support Task"
	wf.is_active = 1
	wf.override_status = 0
	wf.send_email_alert = 0
	wf.workflow_state_field = "status"

	for s in task_states:
		wf.append(
			"states",
			{
				"state": s,
				"doc_status": "0",
				"allow_edit": ALLOW_EDIT_ROLE,
			},
		)

	for state, action, next_state in transitions:
		wf.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": WORKFLOW_ROLE,
			},
		)

	wf.insert(ignore_permissions=True)


def ensure_acknowledgement_notification():
	name = "Support Ticket Acknowledgement"
	expected_subj = "Printechs Support: ticket #{{ doc.name }}# received"
	body = _support_ticket_acknowledgement_message()

	def _apply_ack_fields(doc):
		doc.subject = expected_subj
		doc.message = body
		if doc.meta.has_field("message_type"):
			doc.message_type = "HTML"

	if frappe.db.exists("Notification", name):
		n = frappe.get_doc("Notification", name)
		changed = False
		if n.subject != expected_subj:
			changed = True
		if SUPPORT_TICKET_ACK_EMAIL_VERSION not in (n.message or ""):
			changed = True
		if n.meta.has_field("message_type") and (n.message_type or "") != "HTML":
			changed = True
		if changed:
			_apply_ack_fields(n)
			n.save(ignore_permissions=True)
		return

	n = frappe.new_doc("Notification")
	n.name = name
	n.document_type = "Support Ticket"
	n.event = "New"
	n.channel = "Email"
	n.enabled = 1
	n.is_standard = 0
	n.condition = "doc.contact_email"
	_apply_ack_fields(n)
	n.append("recipients", {"receiver_by_document_field": "contact_email"})
	n.insert(ignore_permissions=True)


def run_setup():
	ensure_roles()
	ensure_permissions()
	build_support_ticket_workflow()
	build_support_task_workflow()
	ensure_acknowledgement_notification()
	frappe.db.commit()
