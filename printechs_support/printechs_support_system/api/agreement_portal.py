# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Portal user provisioning and notifications when a Support Agreement becomes Active."""

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, get_url

PORTAL_ROLE = "Printechs Support Customer"


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
				user.reset_password(send_email=True)
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
	subject = _("Support agreement {0} is now active").format(doc.name)
	company = frappe.defaults.get_defaults().get("company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	brand = company or frappe.get_system_settings("app_name") or "Printechs"

	print_url = get_url(
		f"/printview?doctype=Support%20Agreement&name={quote(doc.name)}&format=Support%20Agreement%20Standard"
	)

	message = f"""<p>{_("Hello,")}</p>
<p>{_("Your support agreement <b>{0}</b> for customer <b>{1}</b> is now <b>Active</b>.").format(doc.name, doc.customer_name or doc.customer)}</p>
<p><a href="{print_url}">{_("View agreement (print/PDF)")}</a></p>
<p>{_("If you received a separate password setup email, use it to access the support portal.")}</p>
<p>{_("— {0}").format(brand)}</p>"""

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
