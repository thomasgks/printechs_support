# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Portal user provisioning and notifications when a Support Agreement becomes Active."""

from urllib.parse import parse_qs, quote, urlparse

import frappe
from frappe import _
from frappe.utils import cint, escape_html, get_url

PORTAL_ROLE = "Printechs Support Customer"
SUPPORT_PORTAL_URL = "https://support.printechs.com/support-portal"


def provision_agreement_portal_users(doc) -> None:
	"""Create or link Website Users for portal_contacts rows; send password-reset for first-time access."""
	if doc.status != "Active":
		return

	for row in doc.portal_contacts or []:
		if not row.email:
			continue
		email = row.email.strip().lower()
		if not email:
			continue

		user_name = frappe.db.get_value("User", {"email": email}, "name")
		if not user_name:
			user_name = frappe.db.get_value("User", email, "name")

		if user_name:
			user = frappe.get_doc("User", user_name)
		else:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": row.full_name or email.split("@")[0],
					"enabled": 1,
					"user_type": "Website User",
					"send_welcome_email": 0,
				}
			)
			user.append("roles", {"role": PORTAL_ROLE})
			user.insert(ignore_permissions=True)

		roles = {r.role for r in (user.roles or [])}
		if PORTAL_ROLE not in roles:
			user.append("roles", {"role": PORTAL_ROLE})
			user.save(ignore_permissions=True)

		row.portal_user = user.name

		if row.contact:
			try:
				contact = frappe.get_doc("Contact", row.contact)
				if not contact.user:
					contact.user = user.name
					contact.save(ignore_permissions=True)
			except Exception:
				pass

		if not row.invite_sent:
			try:
				user.reload()
				_send_portal_welcome_email(user, doc, row)
				row.invite_sent = 1
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Support Agreement portal invite")

		if row.name:
			frappe.db.set_value(
				"Support Agreement Portal Contact",
				row.name,
				{"portal_user": row.portal_user, "invite_sent": cint(row.invite_sent)},
			)


def send_agreement_active_email(doc) -> None:
	"""Notify portal contacts that the agreement is active (print link + optional signed attachment)."""
	subject = _("Your Printechs support portal is ready")
	brand = _brand_name()
	customer = escape_html(doc.customer_name or doc.customer or "")
	agreement_name = escape_html(doc.name)

	print_url = get_url(
		f"/printview?doctype=Support%20Agreement&name={quote(doc.name)}&format=Support%20Agreement%20Standard"
	)

	message = _email_shell(
		brand,
		_("Your support agreement is active"),
		f"""
		<p style="margin:0 0 14px 0;">{_("Hello,")}</p>
		<p style="margin:0 0 16px 0;">{_("Your support agreement")} <strong>{agreement_name}</strong> {_("for customer")} <strong>{customer}</strong> {_("is now active.")}</p>
		<p style="margin:0 0 18px 0;">{_("You can open the Printechs Support Portal to create tickets, follow updates, and review your support activity.")}</p>
		{_button(SUPPORT_PORTAL_URL, _("OPEN SUPPORT PORTAL"))}
		<p style="margin:18px 0 0 0;font-size:13px;color:#64748b;">{_("Agreement copy:")} <a href="{print_url}" style="color:#1d4ed8;text-decoration:none;">{_("View agreement (print/PDF)")}</a></p>
		<p style="margin:12px 0 0 0;font-size:13px;color:#64748b;">{_("Portal link:")} <a href="{SUPPORT_PORTAL_URL}" style="color:#1d4ed8;word-break:break-all;">{SUPPORT_PORTAL_URL}</a></p>
		""",
	)

	recipients = list({r.email.strip().lower() for r in (doc.portal_contacts or []) if r.email})
	if not recipients:
		return

	attachments = _signed_copy_attachments(doc)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		attachments=attachments or None,
	)


def _send_portal_welcome_email(user, doc, row) -> None:
	"""Send a branded first-access email with password setup and the support portal URL."""
	send_portal_welcome_email(
		user,
		customer_name=doc.customer_name or doc.customer or "",
		full_name=row.full_name,
	)


def send_portal_welcome_email(user, customer_name: str | None = None, full_name: str | None = None) -> None:
	"""Send a branded first-access email with password setup and the support portal URL."""
	if isinstance(user, str):
		user = frappe.get_doc("User", user)
	user.db_set("redirect_url", SUPPORT_PORTAL_URL, update_modified=False)
	setup_link = _portal_registration_url(user.reset_password(send_email=False))
	brand = _brand_name()
	first_name = escape_html(user.first_name or full_name or user.email or _("there"))
	customer = escape_html(customer_name or _("your organization"))
	subject = _("Welcome to the Printechs Support Portal")
	message = _email_shell(
		brand,
		_("Welcome to Printechs Support"),
		f"""
		<p style="margin:0 0 14px 0;">{_("Hello")} {first_name},</p>
		<p style="margin:0 0 16px 0;">{_("Your access to the Printechs Support Portal has been created for")} <strong>{customer}</strong>.</p>
		<p style="margin:0 0 18px 0;">{_("Please set your password using the secure button below. After your password is set, you will be taken to the support portal.")}</p>
		{_button(setup_link, _("SET PASSWORD"))}
		<p style="margin:18px 0 0 0;font-size:13px;color:#64748b;">{_("You can use the portal to raise support tickets, track status, and view updates from our team.")}</p>
		<p style="margin:12px 0 0 0;font-size:13px;color:#64748b;">{_("Support portal:")} <a href="{SUPPORT_PORTAL_URL}" style="color:#1d4ed8;word-break:break-all;">{SUPPORT_PORTAL_URL}</a></p>
		<p style="margin:12px 0 0 0;font-size:12px;color:#94a3b8;">{_("If the button does not work, copy and paste this setup link into your browser:")}<br><a href="{setup_link}" style="color:#1d4ed8;word-break:break-all;">{setup_link}</a></p>
		""",
	)
	frappe.sendmail(
		recipients=[user.email],
		subject=subject,
		message=message,
		now=True,
	)


def _brand_name() -> str:
	company = frappe.defaults.get_defaults().get("company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	return company or frappe.get_system_settings("app_name") or "Printechs"


def _portal_registration_url(reset_link: str) -> str:
	key = (parse_qs(urlparse(reset_link).query).get("key") or [""])[0]
	if not key:
		return reset_link
	return f"{SUPPORT_PORTAL_URL}/complete-registration?key={quote(key)}"


def _email_shell(brand: str, title: str, body: str) -> str:
	brand = escape_html(brand)
	title = escape_html(title)
	return f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0;padding:24px 12px;background:#f1f5f9;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
  <tr>
    <td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 10px 40px -18px rgba(15,23,42,0.25);">
        <tr>
          <td style="padding:26px 30px 18px 30px;background:#0f172a;">
            <div style="font-size:13px;font-weight:700;color:#93c5fd;letter-spacing:0.08em;text-transform:uppercase;">{brand}</div>
            <div style="margin-top:8px;font-size:26px;font-weight:800;color:#ffffff;line-height:1.2;">{title}</div>
          </td>
        </tr>
        <tr>
          <td style="padding:26px 30px 28px 30px;font-size:15px;line-height:1.6;color:#334155;">
            {body.strip()}
          </td>
        </tr>
        <tr>
          <td style="border-top:1px solid #e2e8f0;padding:18px 30px 22px 30px;background:#f8fafc;font-size:12px;line-height:1.5;color:#64748b;">
            {_("Need help? Reply to this email or contact the Printechs Support team.")}
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
""".strip()


def _button(url: str, label: str) -> str:
	return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0;">
  <tr>
    <td bgcolor="#1d4ed8" style="border-radius:9px;">
      <a href="{url}" style="display:inline-block;padding:13px 28px;font-size:14px;font-weight:800;color:#ffffff;text-decoration:none;letter-spacing:0.04em;">{escape_html(label)}</a>
    </td>
  </tr>
</table>
""".strip()


def _signed_copy_attachments(doc):
	if not doc.signed_copy:
		return []
	try:
		files = frappe.get_all(
			"File",
			filters={"file_url": doc.signed_copy, "is_folder": 0},
			fields=["name"],
			limit=1,
		)
		if not files:
			return []
		f = frappe.get_doc("File", files[0].name)
		path = f.get_full_path()
		with open(path, "rb") as fh:
			return [{"fname": f.file_name or "signed_agreement.pdf", "fcontent": fh.read()}]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Support Agreement email attachment")
		return []


def mark_expired_support_agreements():
	"""Daily job: set Expired when Valid To date has passed."""
	t = frappe.utils.today()
	frappe.db.sql(
		"""
		UPDATE `tabSupport Agreement`
		SET status = 'Expired'
		WHERE status IN ('Active', 'Signed')
		AND valid_to IS NOT NULL AND valid_to < %s
		""",
		(t,),
	)
