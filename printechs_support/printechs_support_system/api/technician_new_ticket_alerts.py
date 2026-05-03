# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Email + Expo push to technicians when a new customer Support Ticket is created."""

from __future__ import annotations

from html import escape as html_escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_url, strip_html

from printechs_support.permissions import _internal_roles
from printechs_support.printechs_support_system.api.mobile_push import send_expo_push_to_users


def _normalize_email(addr: str | None) -> str | None:
	if not addr or not str(addr).strip():
		return None
	try:
		from frappe.utils import validate_email_address

		s = str(addr).strip()
		validate_email_address(s, True)
		return s.lower()
	except Exception:
		return None


def _user_email(user_id: str | None) -> str | None:
	if not user_id:
		return None
	return _normalize_email(frappe.db.get_value("User", user_id, "email"))


def collect_technician_emails_for_new_ticket(doc) -> list[str]:
	"""Team inbox + team lead + team member emails + assignees (deduped)."""
	seen: set[str] = set()
	out: list[str] = []

	def add(addr: str | None) -> None:
		e = _normalize_email(addr)
		if e and e not in seen:
			seen.add(e)
			out.append(e)

	team = getattr(doc, "team", None)
	if team:
		try:
			st = frappe.get_doc("Support Team", team)
		except Exception:
			st = None
		if st:
			add(getattr(st, "default_email", None))
			add(getattr(st, "team_lead_email", None))
			for row in st.team_members or []:
				add(_user_email(row.get("user")))

	at = getattr(doc, "assigned_to", None)
	add(_user_email(at))

	for row in getattr(doc, "ticket_assignees", None) or []:
		add(_user_email(row.get("user")))

	return out


def collect_technician_user_ids_for_push(doc) -> list[str]:
	"""Users to receive Expo push: assignees + Support Team members + team lead (Employee user)."""
	users: set[str] = set()

	at = getattr(doc, "assigned_to", None)
	if at and frappe.db.get_value("User", at, "enabled"):
		users.add(at)

	for row in getattr(doc, "ticket_assignees", None) or []:
		u = row.get("user")
		if u and frappe.db.get_value("User", u, "enabled"):
			users.add(u)

	team = getattr(doc, "team", None)
	if team:
		try:
			st = frappe.get_doc("Support Team", team)
		except Exception:
			st = None
		if st:
			for row in st.team_members or []:
				u = row.get("user")
				if u and frappe.db.get_value("User", u, "enabled"):
					users.add(u)
			tl = getattr(st, "team_lead", None)
			if tl:
				uid = frappe.db.get_value("Employee", tl, "user_id")
				if uid and frappe.db.get_value("User", uid, "enabled"):
					users.add(uid)

	# Do not push to pure portal-customer accounts (misconfiguration safety).
	internal = _internal_roles()
	out: list[str] = []
	for uid in users:
		if uid in ("Guest",):
			continue
		roles = set(frappe.get_roles(uid))
		if "Printechs Support Customer" in roles and not (roles & internal):
			continue
		out.append(uid)

	return list(dict.fromkeys(out))


def _support_portal_ticket_url(ticket_name: str) -> str:
	base = get_url().rstrip("/")
	return f"{base}/support-portal/tickets/{quote(ticket_name)}"


def _description_for_email_html(description: str | None, *, max_chars: int = 3500) -> str:
	"""Plain text from HTML description, escaped and safe for an email fragment."""
	raw = strip_html(description or "").strip()
	if not raw:
		return f'<span style="color:#94a3b8;font-style:italic;">{html_escape(_("No description provided."))}</span>'
	s = html_escape(raw)
	if len(s) > max_chars:
		s = s[: max_chars - 1] + "…"
	return s.replace("\n", "<br/>")


def _technician_new_ticket_email_html(doc, *, portal_url: str) -> str:
	"""HTML body for internal new-ticket alert (single portal CTA — no Desk / raw URL block)."""
	subj = doc.subject or ""
	customer_label = doc.customer_name or doc.customer or "—"
	ch = str(doc.channel or "—")
	team = (getattr(doc, "team", None) or "").strip() or "—"
	brand = (
		(frappe.defaults.get_defaults().get("company") or "").strip()
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_system_settings("app_name")
		or "Printechs"
	)
	title = html_escape(_("New customer support ticket"))
	ticket_l = html_escape(doc.name)
	subj_e = html_escape(subj)
	cust_e = html_escape(str(customer_label))
	ch_e = html_escape(ch)
	team_e = html_escape(team)
	brand_e = html_escape(str(brand))
	bi = html_escape((brand or "P")[:1].upper())
	portal_btn = html_escape(_("OPEN IN PORTAL"))
	hint = html_escape(_("Sign in to the support portal if you are asked to authenticate."))
	desc_label = html_escape(_("Description"))
	desc_html = _description_for_email_html(getattr(doc, "description", None))

	return f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0;padding:24px 12px;background:#f1f5f9;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 10px 40px -18px rgba(15,23,42,0.2);">
      <tr>
        <td style="padding:22px 26px 8px 26px;">
          <table role="presentation" width="100%"><tr>
            <td width="48" valign="top">
              <div style="width:42px;height:42px;background:#1d4ed8;border-radius:8px;line-height:42px;text-align:center;color:#ffffff;font-weight:700;font-size:18px;">{bi}</div>
            </td>
            <td valign="middle" style="padding-left:8px;">
              <div style="font-size:20px;font-weight:700;color:#0f172a;letter-spacing:-0.02em;">{title}</div>
              <div style="margin-top:4px;font-size:13px;color:#64748b;">{brand_e} · {ticket_l}</div>
            </td>
          </tr></table>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 26px 6px 26px;font-size:15px;line-height:1.55;color:#334155;">
          <p style="margin:0 0 14px 0;">{html_escape(_("A new ticket was raised from the portal or desk."))}</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size:14px;color:#475569;">
            <tr><td style="padding:4px 0;"><b>{html_escape(_("Ticket"))}</b></td><td>{ticket_l}</td></tr>
            <tr><td style="padding:4px 0;"><b>{html_escape(_("Subject"))}</b></td><td>{subj_e}</td></tr>
            <tr><td style="padding:4px 0;"><b>{html_escape(_("Customer"))}</b></td><td>{cust_e}</td></tr>
            <tr><td style="padding:4px 0;"><b>{html_escape(_("Channel"))}</b></td><td>{ch_e}</td></tr>
            <tr><td style="padding:4px 0;"><b>{html_escape(_("Team"))}</b></td><td>{team_e}</td></tr>
          </table>
          <div style="margin-top:16px;padding-top:14px;border-top:1px solid #e2e8f0;">
            <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">{desc_label}</div>
            <div style="font-size:14px;color:#334155;line-height:1.55;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;">{desc_html}</div>
          </div>
        </td>
      </tr>
      <tr>
        <td align="center" style="padding:8px 26px 26px 26px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:12px auto 0 auto;">
            <tr>
              <td bgcolor="#1d4ed8" style="border-radius:10px;">
                <a href="{html_escape(portal_url)}" style="display:inline-block;padding:14px 36px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.06em;">{portal_btn}</a>
              </td>
            </tr>
          </table>
          <p style="margin:14px 0 0 0;font-size:12px;color:#94a3b8;max-width:420px;text-align:center;line-height:1.45;">{hint}</p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>"""


def notify_technicians_new_customer_ticket(ticket_name: str) -> None:
	"""Send team + assignee emails and Expo push (technician devices) for a new customer ticket."""
	if getattr(frappe.flags, "in_test", False):
		return
	try:
		doc = frappe.get_doc("Support Ticket", ticket_name)
	except Exception:
		return

	if (doc.work_scope or "") != "Customer":
		return

	emails = collect_technician_emails_for_new_ticket(doc)
	user_ids = collect_technician_user_ids_for_push(doc)

	subject = _("[{0}] New ticket — {1}").format(doc.name, doc.subject or _("(no subject)"))
	portal_link = _support_portal_ticket_url(doc.name)

	html = _technician_new_ticket_email_html(doc, portal_url=portal_link)

	if emails:
		try:
			frappe.sendmail(
				recipients=emails,
				subject=subject,
				message=html,
				reference_doctype="Support Ticket",
				reference_name=doc.name,
				with_container=True,
				add_unsubscribe_link=0,
				delayed=False,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Printechs new ticket technician email")

	if user_ids:
		try:
			push_body = doc.subject or doc.name
			desc_plain = strip_html(doc.description or "").strip()
			if desc_plain:
				push_body = f"{push_body} — {desc_plain}"[:400]
			else:
				push_body = push_body[:400]
			send_expo_push_to_users(
				user_ids,
				title=_("New ticket {0}").format(doc.name),
				body=push_body,
				data={
					"type": "new_customer_ticket",
					"ticket_name": doc.name,
					"customer": doc.customer or "",
				},
				ticket_name=doc.name,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Printechs new ticket technician push")
