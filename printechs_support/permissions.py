# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Portal and desk permission rules for Support Ticket / Support Task."""

import frappe


def _primary_email_for_user(user: str) -> str:
	"""Lowercased email for matching Contacts and agreement rows."""
	e = frappe.db.get_value("User", user, "email")
	if e:
		return e.strip().lower()
	if user and "@" in user:
		return user.strip().lower()
	return ""


def _contact_names_for_portal_user(user: str) -> list[str]:
	"""Resolve Contact document name(s) for this User (link, email_id, case-insensitive, child emails)."""
	names: list[str] = []
	email_norm = _primary_email_for_user(user)

	if c := frappe.db.get_value("Contact", {"user": user}, "name"):
		names.append(c)

	raw_email = (frappe.db.get_value("User", user, "email") or "").strip()
	if raw_email:
		if c := frappe.db.get_value("Contact", {"email_id": raw_email}, "name"):
			if c not in names:
				names.append(c)

	if email_norm:
		for (cname,) in frappe.db.sql(
			"""
			SELECT name FROM `tabContact`
			WHERE LOWER(TRIM(email_id)) = %s
			LIMIT 5
			""",
			(email_norm,),
		):
			if cname not in names:
				names.append(cname)
		for (cname,) in frappe.db.sql(
			"""
			SELECT DISTINCT c.name
			FROM `tabContact` c
			INNER JOIN `tabContact Email` ce ON ce.parent = c.name AND ce.parenttype = 'Contact'
			WHERE LOWER(TRIM(ce.email_id)) = %s
			LIMIT 10
			""",
			(email_norm,),
		):
			if cname not in names:
				names.append(cname)

	if user and "@" in user and user.strip().lower() != email_norm:
		for (cname,) in frappe.db.sql(
			"""
			SELECT name FROM `tabContact`
			WHERE LOWER(TRIM(email_id)) = LOWER(%s)
			LIMIT 5
			""",
			(user.strip(),),
		):
			if cname not in names:
				names.append(cname)

	return names


def _customers_from_portal_agreements(user: str) -> list[str]:
	"""Customers from Support Agreement portal rows (matches provisioned portal_user / email)."""
	em = _primary_email_for_user(user)
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT sa.customer
		FROM `tabSupport Agreement Portal Contact` pc
		INNER JOIN `tabSupport Agreement` sa ON sa.name = pc.parent
		WHERE IFNULL(sa.customer, '') != ''
		  AND (
				pc.portal_user = %s
				OR ( %s != '' AND LOWER(TRIM(pc.email)) = %s )
		  )
		""",
		(user, em, em),
	)
	return [r[0] for r in rows if r[0]]


def _internal_roles() -> set[str]:
	return {
		"System Manager",
		"Administrator",
		"Printechs Support Coordinator",
		"Printechs Support Engineer",
		"Printechs Support Project Manager",
		"Support Team",
	}


def get_allowed_customers(user: str) -> list[str]:
	"""Customers a portal user may access.

	Resolution order (merged, deduped):
	1. User Permission on Customer
	2. Contact → Customer (via ``user`` / ``email_id`` / case-insensitive match / Contact Email rows)
	3. Support Agreement portal contact rows (``portal_user`` or email match → agreement ``customer``)
	"""
	if not user or user == "Guest":
		return []

	out: list[str] = []
	seen: set[str] = set()

	def add(names: list[str]) -> None:
		for n in names:
			if n and n not in seen:
				seen.add(n)
				out.append(n)

	add(
		frappe.get_all(
			"User Permission",
			filters={"user": user, "allow": "Customer"},
			pluck="for_value",
		)
	)

	for contact_name in _contact_names_for_portal_user(user):
		add(
			frappe.get_all(
				"Dynamic Link",
				filters={
					"parent": contact_name,
					"parenttype": "Contact",
					"link_doctype": "Customer",
				},
				pluck="link_name",
			)
		)

	add(_customers_from_portal_agreements(user))

	return out


def _user_sees_all_tickets(user: str) -> bool:
	if user in ("Administrator", "Guest"):
		return True
	return bool(_internal_roles() & set(frappe.get_roles(user)))


def user_sees_all_support_records(user: str) -> bool:
	"""True if desk/internal roles may see all Support Ticket / Support Task records."""
	return _user_sees_all_tickets(user)


def user_can_edit_portal_task_schedule(user: str, task_name: str) -> bool:
	"""Who may change due/planned dates from the portal: internal roles or anyone assigned to the task."""
	if not user or user == "Guest":
		return False
	if user_sees_all_support_records(user):
		return True
	if not task_name or not frappe.db.exists("Support Task", task_name):
		return False
	if frappe.db.get_value("Support Task", task_name, "assigned_to_user") == user:
		return True
	return bool(
		frappe.db.exists("Support Task Assignee", {"parent": task_name, "user": user}),
	)


def user_can_edit_portal_ticket_schedule(user: str, ticket_name: str) -> bool:
	"""Who may change ticket due date from the portal: internal roles or anyone assigned on the ticket."""
	if not user or user == "Guest":
		return False
	if user_sees_all_support_records(user):
		return True
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		return False
	if frappe.db.get_value("Support Ticket", ticket_name, "assigned_to") == user:
		return True
	return bool(
		frappe.db.exists("Support Ticket Assignee", {"parent": ticket_name, "user": user}),
	)


def user_can_access_support_portal(user: str) -> bool:
	"""Who may use the React support portal (session after login)."""
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	if "Printechs Support Customer" in roles:
		return True
	return bool(_internal_roles() & roles)


def support_ticket_query(user: str, doctype: str | None = None) -> str | None:
	if _user_sees_all_tickets(user):
		return None
	if "Printechs Support Customer" not in frappe.get_roles(user):
		return None
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(c) for c in customers)
	return f"`tabSupport Ticket`.customer in ({escaped})"


def support_task_query(user: str, doctype: str | None = None) -> str | None:
	if _user_sees_all_tickets(user):
		return None
	if "Printechs Support Customer" not in frappe.get_roles(user):
		return None
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(c) for c in customers)
	return (
		f"`tabSupport Task`.support_ticket IN ("
		f"SELECT name FROM `tabSupport Ticket` WHERE customer IN ({escaped}))"
	)


def support_ticket_has_permission(doc, ptype=None, user=None, debug=False):
	"""Deny portal users access to tickets outside their customers; None defers to role perms."""
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return None
	if _user_sees_all_tickets(user):
		return None
	if "Printechs Support Customer" not in frappe.get_roles(user):
		return None
	customers = get_allowed_customers(user)
	if not customers or doc.get("customer") not in customers:
		return False
	return None


def support_task_has_permission(doc, ptype=None, user=None, debug=False):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return None
	if _user_sees_all_tickets(user):
		return None
	if "Printechs Support Customer" not in frappe.get_roles(user):
		return None
	customers = get_allowed_customers(user)
	if not customers:
		return False
	ticket = doc.get("support_ticket")
	if not ticket:
		return False
	cust = frappe.db.get_value("Support Ticket", ticket, "customer")
	if cust not in customers:
		return False
	return None
