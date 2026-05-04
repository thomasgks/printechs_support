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


def _unrestricted_support_ticket_catalog_roles() -> frozenset[str]:
	"""Roles that may list and open every Support Ticket / related tasks (desk + portal)."""
	return frozenset(
		{
			"Administrator",
			"System Manager",
			"Printechs Support Coordinator",
			"Printechs Support Project Manager",
		}
	)


def user_has_unrestricted_support_ticket_catalog(user: str) -> bool:
	"""True when the user must not be limited to their Support Team queue(s)."""
	if not user or user == "Guest":
		return False
	return bool(_unrestricted_support_ticket_catalog_roles() & set(frappe.get_roles(user)))


def get_support_team_names_for_user(user: str) -> list[str]:
	"""Support Team document names where ``user`` is a member or the team lead (Employee → User)."""
	if not user or user == "Guest":
		return []
	out: list[str] = []
	seen: set[str] = set()
	for (name,) in frappe.db.sql(
		"""
		SELECT DISTINCT parent FROM `tabSupport Team Member`
		WHERE user = %s AND IFNULL(parent, '') != ''
		""",
		(user,),
	):
		if name not in seen:
			seen.add(name)
			out.append(name)
	for (name,) in frappe.db.sql(
		"""
		SELECT DISTINCT st.name
		FROM `tabSupport Team` st
		INNER JOIN `tabEmployee` e ON e.name = st.team_lead
		WHERE IFNULL(st.team_lead, '') != '' AND e.user_id = %s
		""",
		(user,),
	):
		if name not in seen:
			seen.add(name)
			out.append(name)
	return out


def internal_user_may_access_support_ticket(user: str, ticket_name: str | None) -> bool:
	"""Whether an internal support user may open this ticket (team queue, assignee, or primary assign)."""
	if not user or not ticket_name:
		return False
	row = frappe.db.get_value(
		"Support Ticket",
		ticket_name,
		["team", "assigned_to"],
		as_dict=True,
	)
	if not row:
		return False
	teams = get_support_team_names_for_user(user)
	if row.get("team") and teams and row.team in teams:
		return True
	if row.get("assigned_to") == user:
		return True
	if frappe.db.exists("Support Ticket Assignee", {"parent": ticket_name, "user": user}):
		return True
	return False


def support_ticket_scope_filters_for_lists(user: str) -> dict:
	"""Fr filters for Support Ticket list/count APIs (portal + dashboard).

	- ``{}`` — no restriction (full catalog).
	- ``{"empty": True}`` — caller should return zero rows.
	- Otherwise AND these key/value pairs (e.g. ``customer`` or ``name`` ``in`` list).
	"""
	if not user or user == "Guest":
		return {"empty": True}
	if user_has_unrestricted_support_ticket_catalog(user):
		return {}
	roles = set(frappe.get_roles(user))
	customers = get_allowed_customers(user)
	is_internal = _user_sees_all_tickets(user)
	is_customer_role = "Printechs Support Customer" in roles

	if is_internal and is_customer_role and customers:
		cust_ids = set(
			frappe.get_all(
				"Support Ticket",
				filters={"customer": ["in", customers]},
				pluck="name",
				limit_page_length=50000,
			)
		)
		team_f = _team_scoped_support_ticket_filters(user)
		team_ids: set[str] = set()
		if not team_f.get("empty"):
			raw = team_f.get("name")
			if isinstance(raw, list) and len(raw) >= 2 and raw[0] == "in":
				team_ids = set(raw[1] or [])
		merged = cust_ids | team_ids
		if not merged:
			return {"empty": True}
		return {"name": ["in", sorted(merged)]}

	if is_internal:
		return _team_scoped_support_ticket_filters(user)

	if not customers:
		return {"empty": True}
	return {"customer": ["in", customers]}


def _team_scoped_support_ticket_filters(user: str) -> dict:
	teams = get_support_team_names_for_user(user)
	assignee_tickets = frappe.get_all(
		"Support Ticket Assignee",
		filters={"user": user},
		pluck="parent",
		limit_page_length=50000,
	)
	ids: set[str] = set(assignee_tickets)
	ids.update(
		frappe.get_all(
			"Support Ticket",
			filters={"assigned_to": user},
			pluck="name",
			limit_page_length=50000,
		)
	)
	if teams:
		ids.update(
			frappe.get_all(
				"Support Ticket",
				filters={"team": ["in", teams]},
				pluck="name",
				limit_page_length=50000,
			)
		)
	if not ids:
		return {"empty": True}
	return {"name": ["in", sorted(ids)]}


def support_task_scope_filters_for_lists(user: str) -> dict:
	"""Fr filters for Support Task list/count (portal): same visibility as tickets + direct assignment."""
	if not user or user == "Guest":
		return {"empty": True}
	if user_has_unrestricted_support_ticket_catalog(user):
		return {}
	roles = set(frappe.get_roles(user))
	customers = get_allowed_customers(user)
	is_internal = _user_sees_all_tickets(user)
	is_customer_role = "Printechs Support Customer" in roles

	if not is_internal:
		if not customers:
			return {"empty": True}
		tickets = frappe.get_all(
			"Support Ticket",
			filters={"customer": ["in", customers]},
			pluck="name",
			limit_page_length=50000,
		)
		if not tickets:
			return {"empty": True}
		return {"support_ticket": ["in", tickets]}

	if is_internal and is_customer_role and customers:
		cust_tickets = set(
			frappe.get_all(
				"Support Ticket",
				filters={"customer": ["in", customers]},
				pluck="name",
				limit_page_length=50000,
			)
		)
		team_f = _team_scoped_support_ticket_filters(user)
		team_tickets: set[str] = set()
		if not team_f.get("empty"):
			raw = team_f.get("name")
			if isinstance(raw, list) and len(raw) >= 2 and raw[0] == "in":
				team_tickets = set(raw[1] or [])
		ticket_union = cust_tickets | team_tickets
		task_ids: set[str] = set(
			frappe.get_all(
				"Support Task",
				filters={"assigned_to_user": user},
				pluck="name",
				limit_page_length=50000,
			)
		)
		task_ids.update(
			frappe.get_all(
				"Support Task Assignee",
				filters={"user": user},
				pluck="parent",
				limit_page_length=50000,
			)
		)
		if ticket_union:
			task_ids.update(
				frappe.get_all(
					"Support Task",
					filters={"support_ticket": ["in", list(ticket_union)]},
					pluck="name",
					limit_page_length=50000,
				)
			)
		if not task_ids:
			return {"empty": True}
		return {"name": ["in", sorted(task_ids)]}

	ticket_scope = _team_scoped_support_ticket_filters(user)
	if ticket_scope.get("empty"):
		allowed_ticket_names: list[str] = []
	else:
		raw = ticket_scope.get("name")
		if isinstance(raw, list) and len(raw) >= 2 and raw[0] == "in":
			allowed_ticket_names = list(raw[1] or [])
		else:
			allowed_ticket_names = []

	task_ids: set[str] = set(
		frappe.get_all(
			"Support Task",
			filters={"assigned_to_user": user},
			pluck="name",
			limit_page_length=50000,
		)
	)
	task_ids.update(
		frappe.get_all(
			"Support Task Assignee",
			filters={"user": user},
			pluck="parent",
			limit_page_length=50000,
		)
	)
	if allowed_ticket_names:
		task_ids.update(
			frappe.get_all(
				"Support Task",
				filters={"support_ticket": ["in", allowed_ticket_names]},
				pluck="name",
				limit_page_length=50000,
			)
		)
	if not task_ids:
		return {"empty": True}
	return {"name": ["in", sorted(task_ids)]}


def _support_ticket_team_scope_sql(user: str, table_alias: str = "tabSupport Ticket") -> str:
	"""SQL boolean fragment for team-scoped internal users (Desk permission query)."""
	esc = frappe.db.escape
	u = esc(user)
	tq = f"`{table_alias.strip('`')}`"
	parts: list[str] = [f"{tq}.`assigned_to` = {u}"]
	parts.append(
		f"EXISTS (SELECT 1 FROM `tabSupport Ticket Assignee` sta "
		f"WHERE sta.parent = {tq}.`name` AND sta.user = {u})"
	)
	teams = get_support_team_names_for_user(user)
	if teams:
		tl = ", ".join(esc(t) for t in teams)
		parts.append(f"{tq}.`team` IN ({tl})")
	return "(" + " OR ".join(parts) + ")"


def support_ticket_permission_query_conditions(user: str, doctype: str | None = None) -> str | None:
	if not user or user == "Guest":
		return "1=0"
	if user == "Administrator":
		return None
	if user_has_unrestricted_support_ticket_catalog(user):
		return None
	if _user_sees_all_tickets(user):
		team_sql = _support_ticket_team_scope_sql(user, "tabSupport Ticket")
		if "Printechs Support Customer" in frappe.get_roles(user):
			customers = get_allowed_customers(user)
			if customers:
				escaped = ", ".join(frappe.db.escape(c) for c in customers)
				cust_sql = f"`tabSupport Ticket`.customer IN ({escaped})"
				return f"({cust_sql} OR {team_sql})"
		return team_sql
	if "Printechs Support Customer" not in frappe.get_roles(user):
		return None
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(c) for c in customers)
	return f"`tabSupport Ticket`.customer IN ({escaped})"


def support_task_permission_query_conditions(user: str, doctype: str | None = None) -> str | None:
	if not user or user == "Guest":
		return "1=0"
	if user == "Administrator":
		return None
	if user_has_unrestricted_support_ticket_catalog(user):
		return None
	if _user_sees_all_tickets(user):
		esc = frappe.db.escape
		u = esc(user)
		ticket_scope = _support_ticket_team_scope_sql(user, "st")
		assignee_task = (
			f"EXISTS (SELECT 1 FROM `tabSupport Task Assignee` tsa "
			f"WHERE tsa.parent = `tabSupport Task`.name AND tsa.user = {u})"
		)
		standalone = (
			f"(IFNULL(`tabSupport Task`.support_ticket, '') = '' "
			f"AND (`tabSupport Task`.assigned_to_user = {u} OR {assignee_task}))"
		)
		team_linked = (
			f"(IFNULL(`tabSupport Task`.support_ticket, '') != '' "
			f"AND EXISTS (SELECT 1 FROM `tabSupport Ticket` st "
			f"WHERE st.name = `tabSupport Task`.support_ticket AND {ticket_scope}))"
		)
		if "Printechs Support Customer" in frappe.get_roles(user):
			customers = get_allowed_customers(user)
			if customers:
				escaped = ", ".join(esc(c) for c in customers)
				cust_linked = (
					f"(IFNULL(`tabSupport Task`.support_ticket, '') != '' "
					f"AND EXISTS (SELECT 1 FROM `tabSupport Ticket` stc "
					f"WHERE stc.name = `tabSupport Task`.support_ticket AND stc.customer IN ({escaped})))"
				)
				return f"({standalone} OR {cust_linked} OR {team_linked})"
		return f"({standalone} OR {team_linked})"
	if "Printechs Support Customer" not in frappe.get_roles(user):
		return None
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(c) for c in customers)
	return (
		f"IFNULL(`tabSupport Task`.support_ticket, '') != '' AND "
		f"`tabSupport Task`.support_ticket IN ("
		f"SELECT name FROM `tabSupport Ticket` WHERE customer IN ({escaped}))"
	)


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
	"""Who may change due/planned dates from the portal: internal roles or assignees.

	Portal customer users must not change due dates on their own (even if Desk grants Write on the
	doc); technicians often use ``Printechs Support Customer`` plus assignment — assignee checks above
	handle that path.
	"""
	if not user or user == "Guest":
		return False
	if user_has_unrestricted_support_ticket_catalog(user):
		return True
	if user_sees_all_support_records(user):
		if not task_name or not frappe.db.exists("Support Task", task_name):
			return False
		tn = frappe.db.get_value("Support Task", task_name, "support_ticket")
		if tn:
			return internal_user_may_access_support_ticket(user, tn)
		if frappe.db.get_value("Support Task", task_name, "assigned_to_user") == user:
			return True
		if frappe.db.exists("Support Task Assignee", {"parent": task_name, "user": user}):
			return True
		return False
	if not task_name or not frappe.db.exists("Support Task", task_name):
		return False
	if frappe.db.get_value("Support Task", task_name, "assigned_to_user") == user:
		return True
	if frappe.db.exists("Support Task Assignee", {"parent": task_name, "user": user}):
		return True
	roles = set(frappe.get_roles(user))
	if "Printechs Support Customer" in roles and not (_internal_roles() & roles):
		return False
	# Custom Desk roles may grant Write without Printechs "internal" roles — avoids a catch-22 when the task is unassigned.
	try:
		return bool(frappe.has_permission("Support Task", "write", doc=task_name, user=user))
	except Exception:
		return False


def user_can_edit_portal_ticket_schedule(user: str, ticket_name: str) -> bool:
	"""Who may change ticket due date from the portal: internal roles or ticket assignees.

	Same rule as tasks: customer portal accounts cannot edit ticket due date unless they are listed
	as assignees (field / child table), even when they have Write on the ticket.
	"""
	if not user or user == "Guest":
		return False
	if user_has_unrestricted_support_ticket_catalog(user):
		return True
	if user_sees_all_support_records(user):
		if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
			return False
		return internal_user_may_access_support_ticket(user, ticket_name)
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		return False
	if frappe.db.get_value("Support Ticket", ticket_name, "assigned_to") == user:
		return True
	if frappe.db.exists("Support Ticket Assignee", {"parent": ticket_name, "user": user}):
		return True
	roles = set(frappe.get_roles(user))
	if "Printechs Support Customer" in roles and not (_internal_roles() & roles):
		return False
	# Same as tasks: Desk Write on this document allows schedule edits even when nobody is assigned yet.
	try:
		return bool(frappe.has_permission("Support Ticket", "write", doc=ticket_name, user=user))
	except Exception:
		return False


def help_article_permission_query_conditions(user: str) -> str:
	if not user:
		user = frappe.session.user
	if user == "Administrator" or user_has_unrestricted_support_ticket_catalog(user):
		return ""
	if user != "Guest" and user_sees_all_support_records(user):
		return "`tabHelp Article`.is_published = 1 AND `tabHelp Article`.show_in_desk = 1"
	return (
		"`tabHelp Article`.is_published = 1 "
		"AND `tabHelp Article`.show_in_portal = 1 "
		"AND `tabHelp Article`.allow_customer_view = 1"
	)


def help_article_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	if permission_type and permission_type.lower() in {"write", "create", "delete", "submit", "cancel"}:
		return user == "Administrator" or bool(
			{"System Manager", "Printechs Support Coordinator", "Printechs Support Engineer"}
			& set(frappe.get_roles(user))
		)
	if user == "Administrator" or user_has_unrestricted_support_ticket_catalog(user):
		return True
	if user != "Guest" and user_sees_all_support_records(user):
		return bool(doc.is_published and doc.show_in_desk)
	return bool(doc.is_published and doc.show_in_portal and doc.allow_customer_view)


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
	"""Legacy hook name: prefer ``support_ticket_permission_query_conditions`` in hooks."""
	return support_ticket_permission_query_conditions(user, doctype)


def support_task_query(user: str, doctype: str | None = None) -> str | None:
	return support_task_permission_query_conditions(user, doctype)


def support_ticket_has_permission(doc, ptype=None, user=None, debug=False):
	"""Deny access outside catalog rules; ``None`` defers to role permission manager."""
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return None
	if user_has_unrestricted_support_ticket_catalog(user):
		return None
	if _user_sees_all_tickets(user):
		if internal_user_may_access_support_ticket(user, doc.get("name")):
			return None
		customers = get_allowed_customers(user)
		if (
			customers
			and doc.get("customer") in customers
			and "Printechs Support Customer" in frappe.get_roles(user)
		):
			return None
		return False
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
	if user_has_unrestricted_support_ticket_catalog(user):
		return None
	if _user_sees_all_tickets(user):
		ticket = doc.get("support_ticket")
		if ticket:
			if internal_user_may_access_support_ticket(user, ticket):
				return None
			customers = get_allowed_customers(user)
			if customers and "Printechs Support Customer" in frappe.get_roles(user):
				cust = frappe.db.get_value("Support Ticket", ticket, "customer")
				if cust and cust in customers:
					return None
			return False
		if doc.get("assigned_to_user") == user:
			return None
		if frappe.db.exists("Support Task Assignee", {"parent": doc.get("name"), "user": user}):
			return None
		return False
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
