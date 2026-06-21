# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Whitelisted methods for the React customer portal (bootstrap + lists)."""

from collections import Counter
from html import escape as html_escape

import frappe
from frappe import _
from frappe.auth import LoginManager
from frappe.core.doctype.user.user import update_password
from frappe.rate_limiter import rate_limit
from frappe.sessions import get_csrf_token

from frappe.utils import (
	add_months,
	add_to_date,
	cint,
	get_datetime,
	get_url,
	getdate,
	now_datetime,
	sanitize_html,
	strip_html,
	today,
)
from frappe.utils.data import sha256_hash
from frappe.utils.file_manager import save_file
from werkzeug.utils import secure_filename

from printechs_support.permissions import (
	get_allowed_customers,
	internal_user_may_access_support_ticket,
	support_task_scope_filters_for_lists,
	support_ticket_scope_filters_for_lists,
	user_can_access_support_portal,
	user_can_edit_portal_task_schedule,
	user_can_edit_portal_ticket_schedule,
	user_has_unrestricted_support_ticket_catalog,
	user_sees_all_support_records,
)
from printechs_support.portal_version_history import format_version_row_for_portal
from printechs_support.printechs_support_system.api.support import get_initial_support_ticket_status


def _assignee_users_by_parent(child_doctype: str, parent_names: list) -> dict[str, list[str]]:
	"""Map parent name -> list of User ids (primary first)."""
	if not parent_names:
		return {}
	rows = frappe.get_all(
		child_doctype,
		filters={"parent": ["in", parent_names]},
		fields=["parent", "user", "is_primary"],
		order_by="idx asc",
	)
	grouped: dict[str, list[tuple[str, int]]] = {}
	for r in rows:
		grouped.setdefault(r.parent, []).append((r.user, cint(r.is_primary)))
	out: dict[str, list[str]] = {}
	for p, pairs in grouped.items():
		pairs.sort(key=lambda x: -x[1])
		out[p] = [u for u, _ in pairs]
	return out


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def get_portal_csrf_token():
	"""Session CSRF for cross-origin portal SPAs (requires ``allow_cors``). Not needed when embedded in Frappe web pages."""
	return get_csrf_token()


@frappe.whitelist()
def register_mobile_push_token(expo_push_token: str | None = None):
	"""Persist Expo push token for the logged-in user (Printechs Support mobile app).

	Call after login so OS notifications can reach this device when staff reply on the ticket.
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	token = (expo_push_token or "").strip()
	if not token:
		frappe.throw(_("Expo push token is required"), frappe.ValidationError)
	if len(token) < 30 or "ExponentPushToken" not in token:
		frappe.throw(_("Invalid Expo push token"), frappe.ValidationError)
	frappe.db.set_value("User", user, "printechs_expo_push_token", token[:500])
	return {"ok": True}


@frappe.whitelist()
def send_test_mobile_push(user: str | None = None):
	"""Send one Expo push to verify FCM/EAS + server wiring.

	- Default: sends to **current user** (must have ``register_mobile_push_token`` already).
	- Optional ``user``: only **Administrator** or **System Manager** may target another User id.

	POST JSON: ``{}`` or ``{ "user": "optional@user.id" }``
	"""
	sess = frappe.session.user
	if not sess or sess == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	target = (user or "").strip() or sess
	if target != sess:
		if sess != "Administrator" and "System Manager" not in frappe.get_roles():
			frappe.throw(_("Only System Manager can send a test push to another user"), frappe.PermissionError)
		if not frappe.db.exists("User", target):
			frappe.throw(_("User not found"), frappe.DoesNotExistError)

	tok = frappe.db.get_value("User", target, "printechs_expo_push_token")
	if not tok or not str(tok).strip():
		frappe.throw(
			_("No Expo push token for this user. Open the mobile app, log in, and let it call register_mobile_push_token."),
			frappe.ValidationError,
		)

	from printechs_support.printechs_support_system.api.mobile_push import send_expo_push_to_users

	send_expo_push_to_users(
		[target],
		title=_("Printechs Support test"),
		body=_("If you see this, push notifications are working."),
		data={"type": "test", "ticket_name": ""},
		ticket_name="TEST-PUSH",
	)
	return {"ok": True, "target": target, "message": _("Test notification sent via Expo.")}


def _portal_login_rate_limit():
	# Default 30 / 15 min per (IP + username): avoids blocking whole offices on one IP (old: 10/IP only).
	# Site can still tune via System Settings → rate_limit_email_link_login (shared key name).
	return cint(frappe.get_system_settings("rate_limit_email_link_login")) or 30


@frappe.whitelist(allow_guest=True)
@rate_limit(key="usr", limit=_portal_login_rate_limit, seconds=15 * 60)
def portal_login(usr: str, pwd: str):
	"""Password login for the standalone portal SPA (Option C). Establishes session + cookies on the bench host."""
	if frappe.get_system_settings("disable_user_pass_login"):
		frappe.throw(_("Login with username and password is not allowed."), frappe.AuthenticationError)

	if not usr or not pwd:
		frappe.throw(_("Email and password are required"), frappe.AuthenticationError)

	frappe.clear_cache(user=usr)
	frappe.local.form_dict["cmd"] = "login"
	frappe.local.form_dict["usr"] = usr.strip()
	frappe.local.form_dict["pwd"] = pwd

	try:
		frappe.local.login_manager = LoginManager()
	except frappe.AuthenticationError:
		raise

	if frappe.session.user == "Guest":
		if frappe.local.response.get("verification"):
			frappe.throw(
				_("Two-factor authentication is required. Use the website login or complete verification."),
				frappe.AuthenticationError,
			)
		if frappe.local.response.get("message") == "Password Reset":
			frappe.throw(
				_("Your password must be reset. Use the website login."),
				frappe.AuthenticationError,
			)
		frappe.throw(_("Invalid login credentials"), frappe.AuthenticationError)

	if not user_can_access_support_portal(frappe.session.user):
		frappe.local.login_manager.logout()
		frappe.throw(
			_(
				"You do not have access to this portal. Ask an administrator to assign the role "
				'"Printechs Support Customer" (or a Printechs/Support Team desk role) to your user, '
				"and ensure the user is enabled."
			),
			frappe.PermissionError,
		)

	frappe.local.response["message"] = "ok"
	return {"logged_in": True}


@frappe.whitelist(allow_guest=True)
@rate_limit(key="key", limit=10, seconds=15 * 60)
def complete_portal_registration(key: str, new_password: str):
	"""Set a new password from a reset key, then keep the user in the support portal."""
	key = (key or "").strip()
	if not key:
		frappe.throw(_("Registration link is missing or invalid."), frappe.ValidationError)
	if not new_password:
		frappe.throw(_("New password is required."), frappe.ValidationError)

	reset_user = frappe.db.get_value("User", {"reset_password_key": sha256_hash(key), "enabled": 1}, "name")
	if not reset_user:
		frappe.throw(
			_("This registration link has expired or was already used. Please request a new welcome email."),
			frappe.ValidationError,
		)
	if reset_user and not user_can_access_support_portal(reset_user):
		frappe.throw(_("This user does not have access to the support portal."), frappe.PermissionError)

	if not getattr(frappe.local, "login_manager", None):
		frappe.local.login_manager = LoginManager()
	redirect_url = update_password(new_password=new_password, key=key)
	user = frappe.session.user
	if user == "Guest" and reset_user:
		frappe.local.login_manager.login_as(reset_user)
		user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Could not complete registration. Please try the link again."), frappe.AuthenticationError)
	if not user_can_access_support_portal(user):
		frappe.local.login_manager.logout()
		frappe.throw(_("This user does not have access to the support portal."), frappe.PermissionError)

	return {"logged_in": True, "redirect_url": redirect_url or "/support-portal"}


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def portal_web_logout():
	"""Used by portal ``logoutUrl()``: end session and redirect browser to the support portal shell."""
	frappe.local.login_manager.logout()
	frappe.db.commit()
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/support-portal"


@frappe.whitelist(allow_guest=True)
def portal_logout():
	"""End the current portal session for SPA logout calls."""
	frappe.local.login_manager.logout()
	frappe.db.commit()
	return {"logged_out": True}


def _portal_help_url() -> str:
	try:
		url = (frappe.db.get_single_value("Printechs Support Settings", "help_url") or "").strip()
	except Exception:
		url = ""
	if not url:
		return "/help-center"
	if url.startswith(("http://", "https://", "/")):
		return url
	return f"/{url}"


def _portal_brand_context() -> dict[str, str]:
	logo = ""
	try:
		from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

		logo = get_app_logo() or ""
	except Exception:
		logo = ""

	brand_name = (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_system_settings("app_name")
		or "Printechs Support"
	)
	return {"brand_logo": logo, "brand_name": brand_name}


@frappe.whitelist(allow_guest=True)
def get_portal_bootstrap():
	"""Called on SPA load; guests must be allowed so we can show sign-in (not a misleading 'not whitelisted' error)."""
	user = frappe.session.user
	if user == "Guest":
		return {"logged_in": False}

	full_name = frappe.db.get_value("User", user, "full_name") or user
	customers = get_allowed_customers(user)
	internal = user_sees_all_support_records(user)
	brand = _portal_brand_context()

	return {
		"logged_in": True,
		"user": user,
		"full_name": full_name,
		"customers": customers,
		"internal": internal,
		"help_url": _portal_help_url(),
		"brand_logo": brand["brand_logo"],
		"brand_name": brand["brand_name"],
	}


_VALID_CREATE_PRIORITIES = frozenset({"Low", "Medium", "High", "Critical"})


def _ticket_type_names_from_customer_mapping(customer: str) -> list[str] | None:
	"""Return allowed Support Ticket Type **names** from Customer child table.

	- ``None`` = mapping not used (no rows or DocType missing) → caller may show **all** active types.
	- ``[]`` = mapping exists but no valid types → portal shows **no** types.
	- non-empty list = restrict to these names (still must be active).
	"""
	if not customer or not frappe.db.exists("Customer", customer):
		return None
	if not frappe.db.exists("DocType", "Customer Allowed Ticket Type"):
		return None
	cnt = frappe.db.count(
		"Customer Allowed Ticket Type",
		{
			"parent": customer,
			"parenttype": "Customer",
			"parentfield": "printechs_allowed_ticket_types",
		},
	)
	if cnt == 0:
		return None
	names = frappe.db.sql_list(
		"""
		SELECT ticket_type
		FROM `tabCustomer Allowed Ticket Type`
		WHERE parent=%s AND parenttype='Customer' AND parentfield=%s
		AND IFNULL(ticket_type,'') != ''
		ORDER BY idx ASC
		""",
		(customer, "printechs_allowed_ticket_types"),
	)
	seen: set[str] = set()
	out: list[str] = []
	for n in names:
		if n and n not in seen:
			seen.add(n)
			out.append(n)
	return out


def _active_support_agreement_names_for_portal(customer: str) -> list[str]:
	"""Support Agreement names that are active, portal-visible, allow tickets, and in validity window."""
	if not customer or not frappe.db.exists("Customer", customer):
		return []
	t = today()
	return frappe.db.sql_list(
		"""
		SELECT name FROM `tabSupport Agreement`
		WHERE customer=%s
			AND status='Active'
			AND IFNULL(portal_visible,0)=1
			AND IFNULL(allows_ticket_creation,0)=1
			AND (valid_from IS NULL OR valid_from <= %s)
			AND (valid_to IS NULL OR valid_to >= %s)
		""",
		(customer, t, t),
	)


def _ticket_type_names_from_agreement_mapping(customer: str) -> list[str] | None:
	"""Allowed types from **active** Support Agreements when that child table has rows.

	- ``None`` = no agreement rows → fall back to Customer / all types.
	- ``[]`` / non-empty = same semantics as customer mapping.
	"""
	if not customer:
		return None
	if not frappe.db.exists("DocType", "Customer Allowed Ticket Type"):
		return None
	if not frappe.db.exists("DocType", "Support Agreement"):
		return None
	ags = _active_support_agreement_names_for_portal(customer)
	if not ags:
		return None
	cnt = frappe.db.count(
		"Customer Allowed Ticket Type",
		{
			"parent": ["in", ags],
			"parenttype": "Support Agreement",
			"parentfield": "printechs_agreement_allowed_ticket_types",
		},
	)
	if cnt == 0:
		return None
	rows = frappe.get_all(
		"Customer Allowed Ticket Type",
		filters={
			"parent": ["in", ags],
			"parenttype": "Support Agreement",
			"parentfield": "printechs_agreement_allowed_ticket_types",
		},
		fields=["ticket_type"],
		order_by="idx asc",
	)
	seen: set[str] = set()
	out: list[str] = []
	for r in rows:
		n = (r.get("ticket_type") or "").strip()
		if n and n not in seen:
			seen.add(n)
			out.append(n)
	return out


def _ticket_type_names_from_mapping(customer: str) -> list[str] | None:
	"""Agreement mapping takes precedence over Customer when active agreements define types."""
	ag = _ticket_type_names_from_agreement_mapping(customer)
	if ag is not None:
		return ag
	return _ticket_type_names_from_customer_mapping(customer)


def _resolve_customer_for_portal_ticket_types(user: str, customer: str | None) -> str | None:
	"""Which Customer record to use for ticket-type mapping (may be None → all types)."""
	c = (customer or "").strip()
	if user_sees_all_support_records(user):
		return c or None
	allowed = get_allowed_customers(user)
	if not allowed:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if len(allowed) == 1:
		return allowed[0]
	if not c:
		return None
	if c not in allowed:
		frappe.throw(_("Invalid customer"), frappe.ValidationError)
	return c


@frappe.whitelist()
def get_portal_ticket_types(customer: str | None = None):
	"""Active Support Ticket Types for the create-ticket form (customer and internal users).

	When an **active, portal-visible Support Agreement** has rows in **Allowed ticket types**, those
	take precedence. Otherwise, when the **Customer** has rows in **Portal — Allowed Ticket Types**,
	only those types are returned. If both are empty, all active types are returned.

	:param customer: Optional Customer id; internal users should pass the selected customer.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	cust = _resolve_customer_for_portal_ticket_types(user, customer)

	filters: dict = {"is_active": 1}
	mapped: list[str] | None = None
	if cust:
		mapped = _ticket_type_names_from_mapping(cust)
		if mapped is not None:
			if not mapped:
				return {"types": [], "restricted": True}
			filters["name"] = ["in", mapped]

	rows = frappe.get_all(
		"Support Ticket Type",
		filters=filters,
		fields=["name", "ticket_type_name", "division"],
		order_by="ticket_type_name asc",
		limit_page_length=500,
	)
	return {
		"types": [
			{
				"name": r.name,
				"label": (r.ticket_type_name or r.name).strip(),
				"division": r.division or "",
			}
			for r in rows
		],
		"restricted": mapped is not None,
	}


@frappe.whitelist()
def get_portal_teams():
	"""Active Support Teams for assignment (internal technicians)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_sees_all_support_records(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	rows = frappe.get_all(
		"Support Team",
		filters={"is_active": 1},
		fields=["name", "team_name", "division"],
		order_by="team_name asc",
		limit_page_length=200,
	)
	return {"teams": [{"name": r.name, "label": f"{r.team_name} ({r.division})"} for r in rows]}


_ASSIGNMENT_ROLES = (
	"Printechs Support Engineer",
	"Printechs Support Coordinator",
	"Printechs Support Project Manager",
	"Support Team",
	"System Manager",
)


@frappe.whitelist()
def get_portal_assignment_users(limit: int = 200):
	"""Users that may appear in ticket/task assignment pickers (internal technicians)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_sees_all_support_records(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	limit = min(int(limit), 500)
	placeholders = ",".join(["%s"] * len(_ASSIGNMENT_ROLES))
	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT u.name, u.full_name
		FROM `tabUser` u
		INNER JOIN `tabHas Role` hr ON hr.parent = u.name AND hr.parenttype = 'User'
		WHERE u.enabled = 1 AND u.name != 'Guest'
		AND hr.role IN ({placeholders})
		ORDER BY u.full_name ASC
		LIMIT %s
		""",
		tuple(_ASSIGNMENT_ROLES) + (limit,),
		as_dict=False,
	)
	return {
		"users": [
			{"name": r[0], "full_name": (r[1] or r[0]).strip()}
			for r in rows
			if r[0] and r[0] != "Guest"
		]
	}


@frappe.whitelist()
def get_portal_ticket_customers():
	"""Customers the current user may filter/create Support Tickets for (portal)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if user_has_unrestricted_support_ticket_catalog(user):
		rows = frappe.get_all(
			"Customer",
			fields=["name", "customer_name"],
			order_by="customer_name asc",
			limit_page_length=500,
		)
		return {
			"customers": [{"name": r.name, "customer_name": (r.customer_name or r.name).strip()} for r in rows],
		}

	if user_sees_all_support_records(user):
		scope = support_ticket_scope_filters_for_lists(user)
		if scope.get("empty"):
			return {"customers": []}
		filters = {k: v for k, v in scope.items() if k != "empty"}
		names = frappe.get_all(
			"Support Ticket",
			filters=filters or None,
			pluck="customer",
			distinct=True,
			limit_page_length=500,
		)
	else:
		names = get_allowed_customers(user)

	out = []
	for name in sorted({n for n in names if n}):
		cn = frappe.db.get_value("Customer", name, "customer_name") or name
		out.append({"name": name, "customer_name": str(cn).strip()})
	return {"customers": out}


@frappe.whitelist()
def create_portal_ticket(
	subject: str,
	description: str | None = None,
	priority: str = "Medium",
	customer: str | None = None,
	ticket_type: str | None = None,
	work_scope: str | None = None,
):
	"""Create a Support Ticket from the portal (customer or internal user).

	Internal team members may pass ``work_scope='Internal'`` for test / internal-only tickets (no Customer).
	Portal customers always get customer-facing tickets; any ``work_scope`` other than empty/Customer is rejected.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	subject = (subject or "").strip()
	if not subject:
		frappe.throw(_("Subject is required"), frappe.ValidationError)

	tt = (ticket_type or "").strip()
	if not tt:
		frappe.throw(_("Ticket type is required"), frappe.ValidationError)
	if not frappe.db.exists("Support Ticket Type", tt):
		frappe.throw(_("Invalid ticket type"), frappe.ValidationError)
	if not frappe.db.get_value("Support Ticket Type", tt, "is_active"):
		frappe.throw(_("This ticket type is not active"), frappe.ValidationError)

	priority = (priority or "Medium").strip()
	if priority not in _VALID_CREATE_PRIORITIES:
		frappe.throw(_("Invalid priority"), frappe.ValidationError)

	internal = user_sees_all_support_records(user)
	ws_raw = (work_scope or "").strip()
	want_internal = ws_raw.lower() == "internal"

	if ws_raw and not want_internal and ws_raw.lower() not in ("customer", ""):
		frappe.throw(_("Invalid work scope"), frappe.ValidationError)

	if want_internal:
		if not internal:
			frappe.throw(_("Only internal team members can create internal work-scope tickets."), frappe.PermissionError)
		cust = ""
	else:
		allowed = get_allowed_customers(user)
		cust = (customer or "").strip()

		if internal:
			if not cust:
				frappe.throw(_("Customer is required"), frappe.ValidationError)
			if not frappe.db.exists("Customer", cust):
				frappe.throw(_("Invalid customer"), frappe.ValidationError)
		else:
			if not allowed:
				frappe.throw(
					_(
						"No customer is linked to your user. Ask an administrator to assign User Permissions "
						"or link your user to a Contact for a Customer."
					),
					frappe.PermissionError,
				)
			if len(allowed) == 1:
				cust = allowed[0]
			elif not cust or cust not in allowed:
				frappe.throw(_("Please select a customer"), frappe.ValidationError)

	if not want_internal:
		mapped = _ticket_type_names_from_mapping(cust)
		if mapped is not None:
			if not mapped:
				frappe.throw(
					_(
						"No ticket types are configured for this customer in the portal "
						"(check Support Agreement → Allowed ticket types or Customer → Portal — Allowed Ticket Types)."
					),
					frappe.ValidationError,
				)
			if tt not in mapped:
				frappe.throw(
					_("This ticket type is not allowed for the selected customer."),
					frappe.ValidationError,
				)

	desc = ""
	if description and str(description).strip():
		desc = sanitize_html(str(description).strip())
		if not strip_html(desc).strip():
			desc = ""
	if not desc:
		desc = f"<p>{html_escape(subject)}</p>"

	initial_status = get_initial_support_ticket_status()
	row = {
		"doctype": "Support Ticket",
		"subject": subject,
		"ticket_type": tt,
		"priority": priority,
		"status": initial_status,
		"description": desc,
	}
	if want_internal:
		row["work_scope"] = "Internal"
		row["action_required_from"] = "Technician"
		row["current_owner_type"] = "Technician"
	else:
		row["customer"] = cust
		row["action_required_from"] = "Manager"
		row["current_owner_type"] = "Manager"

	doc = frappe.get_doc(row)
	doc.flags.priority_from_portal = 1
	doc.insert(ignore_permissions=True)

	out = {
		"name": doc.name,
		"subject": doc.subject,
		"status": doc.status,
		"customer": doc.customer or "",
		"work_scope": doc.work_scope or "Customer",
	}
	return out


def _valid_support_task_types() -> list[str]:
	meta = frappe.get_meta("Support Task")
	f = meta.get_field("task_type")
	if not f or not f.options:
		return ["Internal Task"]
	return [x.strip() for x in str(f.options).split("\n") if x.strip()]


_STANDALONE_TASK_DIVISIONS = frozenset({"Software", "Industrial", "Retail"})


def _normalize_optional_ticket(support_ticket) -> str | None:
	"""Treat blank / null-like JSON values as no ticket (internal standalone)."""
	if support_ticket is None:
		return None
	if isinstance(support_ticket, (int, float)):
		if support_ticket == 0:
			return None
		s = str(support_ticket).strip()
		return s if s else None
	s = str(support_ticket).strip()
	if not s or s.lower() in ("null", "none", "undefined"):
		return None
	return s

_PORTAL_TASK_LIST_FIELDS = [
	"name",
	"subject",
	"status",
	"task_type",
	"modified",
	"support_ticket",
	"customer",
	"division",
	"assigned_to_user",
	"due_date",
	"delay_owner",
	"delay_reason",
	"is_delayed",
	"delay_days",
	"creation",
]


def _wire_portal_task_rows(tasks: list) -> None:
	"""Mutate get_all rows: due_date wire + assigned_users."""
	names = [t["name"] for t in tasks]
	amap = _assignee_users_by_parent("Support Task Assignee", names)
	for t in tasks:
		ds, dc = _portal_due_datetime_wire(t.get("due_date"))
		t["due_date"] = ds
		t["due_date_calendar"] = dc
		t["assigned_users"] = amap.get(t["name"], [])


_VALID_TASK_RESPONSIBLE_SIDES = frozenset({"Printechs", "Customer", "Shared"})


@frappe.whitelist()
def create_portal_support_task(
	support_ticket: str | None = None,
	subject: str = "",
	task_type: str | None = None,
	due_date: str | None = None,
	division: str | None = None,
	description: str | None = None,
	responsible_side: str | None = None,
):
	"""Create a Support Task from the portal.

	- With **support_ticket**: any portal user who can see that ticket (scoped customers or internal).
	- Without ticket (**internal team only**): standalone internal task; **division** must be Software / Industrial / Retail.
	- **description**: optional; plain text or HTML (sanitized).
	- **responsible_side**: Printechs / Customer / Shared (default Printechs). Customer is linked from the ticket when set.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = _normalize_optional_ticket(support_ticket)
	subject = (subject or "").strip()
	if not subject:
		frappe.throw(_("Subject is required"), frappe.ValidationError)

	if ticket_name:
		if not frappe.db.exists("Support Ticket", ticket_name):
			frappe.throw(
				_("Support ticket {0} does not exist or you have no access.").format(ticket_name),
				frappe.ValidationError,
			)
		_assert_portal_ticket_access(user, ticket_name)
	else:
		if not user_sees_all_support_records(user):
			frappe.throw(
				_("Only internal team members can create tasks without a support ticket."),
				frappe.PermissionError,
			)
		div = (division or "").strip()
		if not div or div not in _STANDALONE_TASK_DIVISIONS:
			frappe.throw(
				_("Division is required when no ticket is linked (Software, Industrial, or Retail)."),
				frappe.ValidationError,
			)

	valid_types = _valid_support_task_types()
	tt = (task_type or (valid_types[0] if valid_types else "Internal Task")).strip()
	if tt not in valid_types:
		frappe.throw(_("Invalid task type"), frappe.ValidationError)

	rs = (responsible_side or "Printechs").strip()
	if rs not in _VALID_TASK_RESPONSIBLE_SIDES:
		frappe.throw(_("Invalid responsible side"), frappe.ValidationError)

	rows: dict = {
		"doctype": "Support Task",
		"naming_series": "SUP-TSK-.YYYY.-.#####",
		"subject": subject,
		"task_type": tt,
		"status": "Open",
		"responsible_side": rs,
	}
	if ticket_name:
		rows["support_ticket"] = ticket_name
	else:
		rows["division"] = (division or "").strip()

	desc_raw = (description or "").strip() if description else ""
	if desc_raw:
		if "<" in desc_raw:
			desc_val = sanitize_html(desc_raw)
			if not strip_html(desc_val).strip():
				desc_val = ""
		else:
			desc_val = f"<p>{html_escape(desc_raw).replace(chr(10), '<br>')}</p>"
		if desc_val:
			rows["description"] = desc_val

	doc = frappe.get_doc(rows)
	dd = (due_date or "").strip()
	if dd:
		doc.due_date = dd
	doc.insert(ignore_permissions=True)

	return {
		"name": doc.name,
		"subject": doc.subject,
		"status": doc.status,
		"support_ticket": doc.support_ticket or None,
		"division": doc.division or None,
		"responsible_side": doc.responsible_side or "Printechs",
		"customer": doc.customer or None,
	}


@frappe.whitelist()
def get_portal_tickets(
	limit: int = 50,
	search: str | None = None,
	active_only: int | bool = 0,
	customer: str | None = None,
	ticket_type: str | None = None,
):
	"""List tickets for the portal.

	:param search: Optional filter on ticket ID (``name`` contains search string).
	:param active_only: If truthy, exclude Resolved / Closed / Cancelled. Default **0** so callers
		that only pass ``limit`` (older portal bundles) still see all tickets; the SPA sends
		``active_only=1`` when the list should hide closed tickets.
	:param customer: Optional Customer text filter. Matches Customer link or display name inside
		the user's existing ticket scope.
	:param ticket_type: Optional Support Ticket Type filter.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	# Cap above 100 so calendar / heavy lists can request more rows in one call.
	limit = min(int(limit), 300)
	active = bool(cint(active_only))
	q = (search or "").strip()
	customer_filter = (customer or "").strip()
	ticket_type_filter = (ticket_type or "").strip()

	scope = support_ticket_scope_filters_for_lists(user)
	if scope.get("empty"):
		return []

	filters: dict = {k: v for k, v in scope.items() if k != "empty"}

	if active:
		filters["status"] = ["not in", ["Resolved", "Closed", "Cancelled"]]
	if ticket_type_filter:
		filters["ticket_type"] = ticket_type_filter

	customer_or_filters = None
	if customer_filter:
		customer_like = f"%{customer_filter}%"
		customer_or_filters = [
			["Support Ticket", "customer", "like", customer_like],
			["Support Ticket", "customer_name", "like", customer_like],
		]

	if q:
		qn = q.strip()
		if "name" in filters and isinstance(filters["name"], list) and filters["name"][0] == "in":
			allowed = list(filters["name"][1] or [])
			filters["name"] = ["in", [n for n in allowed if qn.lower() in str(n).lower()]]
		else:
			filters["name"] = ["like", f"%{qn}%"]

	rows = frappe.get_all(
		"Support Ticket",
		filters=filters or None,
		or_filters=customer_or_filters,
		fields=[
			"name",
			"subject",
			"status",
			"priority",
			"ticket_type",
			"modified",
			"customer",
			"due_date",
			"assigned_to",
		],
		order_by="modified desc",
		limit_page_length=limit,
	)
	for r in rows:
		ds, dc = _portal_due_datetime_wire(r.get("due_date"))
		r["due_date"] = ds
		r["due_date_calendar"] = dc
		r["ticket_type_label"] = (
			frappe.db.get_value("Support Ticket Type", r.get("ticket_type"), "ticket_type_name")
			if r.get("ticket_type")
			else ""
		) or r.get("ticket_type") or ""
	ticket_names = [r["name"] for r in rows]
	amap_tickets = _assignee_users_by_parent("Support Ticket Assignee", ticket_names)
	for r in rows:
		r["assigned_users"] = amap_tickets.get(r["name"], [])
	return rows


@frappe.whitelist()
def get_portal_tasks(limit: int = 50):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	limit = min(int(limit), 300)

	scope = support_task_scope_filters_for_lists(user)
	if scope.get("empty"):
		return []

	task_filters = {k: v for k, v in scope.items() if k != "empty"}
	tasks = frappe.get_all(
		"Support Task",
		filters=task_filters or None,
		fields=_PORTAL_TASK_LIST_FIELDS,
		order_by="modified desc",
		limit_page_length=limit,
	)

	_wire_portal_task_rows(tasks)
	return tasks


@frappe.whitelist()
def get_portal_tasks_for_ticket(ticket_name: str, limit: int = 100):
	"""Tasks linked to a ticket (portal). Respects the same ticket access rules as get_portal_ticket."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	name = (ticket_name or "").strip()
	if not name or not frappe.db.exists("Support Ticket", name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, name)

	limit = min(int(limit), 300)
	tasks = frappe.get_all(
		"Support Task",
		filters={"support_ticket": name},
		fields=_PORTAL_TASK_LIST_FIELDS,
		order_by="modified desc",
		limit_page_length=limit,
	)
	_wire_portal_task_rows(tasks)
	return tasks


# Resolved still allows customer confirmation / structured workflow replies.
_ARCHIVED_TICKET_STATUSES = frozenset({"Closed", "Cancelled"})
_TERMINAL_TASK_STATUS = ("Completed", "Cancelled")
# Block ad-hoc comments only when archived; use workflow actions on Resolved tickets.
_COMMUNICATION_LOCKED_TICKET_STATUSES = frozenset(_ARCHIVED_TICKET_STATUSES)


def _ticket_communication_locked(status: str | None) -> bool:
	return (status or "").strip() in _COMMUNICATION_LOCKED_TICKET_STATUSES


def _assert_ticket_communication_allowed(ticket_name: str) -> None:
	st = frappe.db.get_value("Support Ticket", ticket_name, "status")
	if _ticket_communication_locked(st):
		frappe.throw(
			_("This ticket is resolved or closed. Reopen it to add messages or attachments."),
			frappe.ValidationError,
		)


def _assert_task_communication_allowed(task_name: str) -> None:
	"""Allow task comments unless the linked ticket is locked, or (standalone task) task is terminal."""
	row = frappe.db.get_value(
		"Support Task",
		task_name,
		["support_ticket", "status"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	if row.support_ticket:
		_assert_ticket_communication_allowed(row.support_ticket)
		return
	st = (row.status or "").strip()
	if st in _TERMINAL_TASK_STATUS:
		frappe.throw(
			_("This task is completed or cancelled. Reopen it in Desk to add messages or attachments."),
			frappe.ValidationError,
		)


def _ticket_scope_filters(user: str) -> dict:
	"""Filters for Support Ticket queries; ``{'empty': True}`` means no visible tickets."""
	return support_ticket_scope_filters_for_lists(user)


def _count_tickets(user: str, filters: dict) -> int:
	scope = _ticket_scope_filters(user)
	if scope.get("empty"):
		return 0
	merged = {**filters, **{k: v for k, v in scope.items() if k != "empty"}}
	return int(frappe.db.count("Support Ticket", merged))


def _ticket_status_counts(user: str) -> dict:
	scope = _ticket_scope_filters(user)
	if scope.get("empty"):
		return {}
	filters = {k: v for k, v in scope.items() if k != "empty"}
	rows = frappe.get_all(
		"Support Ticket",
		filters=filters,
		pluck="status",
		limit_page_length=10000,
	)
	return dict(Counter(rows))


def _task_scope_filters(user: str) -> dict:
	"""Filters for Support Task queries; ``{'empty': True}`` means no visible tasks."""
	return support_task_scope_filters_for_lists(user)


def _count_tasks(user: str, filters: dict) -> int:
	scope = _task_scope_filters(user)
	if scope.get("empty"):
		return 0
	merged = {**filters, **scope}
	return int(frappe.db.count("Support Task", merged))


def _task_status_counts(user: str) -> dict:
	scope = _task_scope_filters(user)
	if scope.get("empty"):
		return {}
	filters = {k: v for k, v in scope.items() if k != "empty"}
	rows = frappe.get_all(
		"Support Task",
		filters=filters,
		pluck="status",
		limit_page_length=10000,
	)
	return dict(Counter(rows))


def _assignee_workload(user: str, limit: int = 8) -> list:
	scope = _task_scope_filters(user)
	if scope.get("empty"):
		return []
	filters = {k: v for k, v in scope.items() if k != "empty"}
	filters["status"] = ["not in", _TERMINAL_TASK_STATUS]
	rows = frappe.get_all(
		"Support Task",
		filters=filters,
		fields=["assigned_to_user"],
		limit_page_length=10000,
	)
	c = Counter((r.get("assigned_to_user") or "Unassigned") for r in rows)
	return [{"name": k, "count": v} for k, v in c.most_common(limit)]


def _monthly_completion_trend(user: str) -> list:
	scope = _task_scope_filters(user)
	if scope.get("empty"):
		return []
	filters = {k: v for k, v in scope.items() if k != "empty"}
	filters["status"] = "Completed"
	rows = frappe.get_all(
		"Support Task",
		filters=filters,
		fields=["modified"],
		limit_page_length=8000,
	)
	c = Counter()
	for r in rows:
		m = r.modified
		if not m:
			continue
		key = str(m)[:7]
		if len(key) == 7:
			c[key] += 1
	today_d = getdate()
	out = []
	for i in range(5, -1, -1):
		d = add_months(today_d, -i)
		key = d.strftime("%Y-%m")
		out.append(
			{
				"month": key,
				"label": d.strftime("%b %Y"),
				"count": int(c.get(key, 0)),
			}
		)
	return out


@frappe.whitelist(allow_guest=True)
def get_portal_dashboard_stats():
	"""Dashboard KPIs + chart payloads (same visibility rules as list APIs).

	Guest must be allowed so unauthenticated RPC does not show Frappe's misleading
	"not whitelisted" error; we reject Guest below (same pattern as get_portal_bootstrap).
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	now = frappe.utils.now()
	today_s = today()

	scope = _task_scope_filters(user)
	if scope.get("empty"):
		return {
			"pending_tickets": 0,
			"overdue_tickets": 0,
			"tickets_waiting_customer": 0,
			"tickets_waiting_internal": 0,
			"pending_tasks": 0,
			"overdue_tasks": 0,
			"completed_today": 0,
			"waiting_customer": 0,
			"waiting_internal": 0,
			"sla_breached": 0,
			"delayed_flagged": 0,
			"tickets_by_status": {},
			"tasks_by_status": {},
			"assignee_load": [],
			"monthly_completion": [],
		}

	active_statuses = ["not in", list(_ARCHIVED_TICKET_STATUSES)]
	pending_tickets = _count_tickets(user, {"status": active_statuses})
	overdue_tickets = _count_tickets(
		user,
		{"due_date": ["<", now], "status": ["not in", ["Closed", "Cancelled", "Resolved"]]},
	)
	tickets_waiting_customer = _count_tickets(user, {"status": "Waiting for Customer"})
	tickets_waiting_internal = _count_tickets(user, {"status": "Waiting for Technician"})
	tickets_by_status = _ticket_status_counts(user)

	pending_tasks = _count_tasks(user, {"status": ["not in", _TERMINAL_TASK_STATUS]})
	overdue_tasks = _count_tasks(
		user,
		{"due_date": ["<", now], "status": ["not in", _TERMINAL_TASK_STATUS]},
	)
	completed_today = _count_tasks(
		user,
		{
			"status": "Completed",
			"modified": ["between", [f"{today_s} 00:00:00", f"{today_s} 23:59:59"]],
		},
	)
	waiting_customer = _count_tasks(user, {"status": "Waiting for Customer"})
	waiting_internal = _count_tasks(user, {"status": "Waiting for Printechs"})
	delayed_flagged = _count_tasks(
		user,
		{"is_delayed": 1, "status": ["not in", _TERMINAL_TASK_STATUS]},
	)
	# Until explicit SLA breach fields exist on Support Task, mirror overdue open tasks.
	sla_breached = overdue_tasks

	tasks_by_status = _task_status_counts(user)
	assignee_load = _assignee_workload(user)
	monthly_completion = _monthly_completion_trend(user)

	return {
		"pending_tickets": int(pending_tickets),
		"overdue_tickets": int(overdue_tickets),
		"tickets_waiting_customer": int(tickets_waiting_customer),
		"tickets_waiting_internal": int(tickets_waiting_internal),
		"pending_tasks": int(pending_tasks),
		"overdue_tasks": int(overdue_tasks),
		"completed_today": int(completed_today),
		"waiting_customer": int(waiting_customer),
		"waiting_internal": int(waiting_internal),
		"sla_breached": int(sla_breached),
		"delayed_flagged": int(delayed_flagged),
		"tickets_by_status": tickets_by_status,
		"tasks_by_status": tasks_by_status,
		"assignee_load": assignee_load,
		"monthly_completion": monthly_completion,
	}


def _assert_portal_ticket_access(user: str, ticket_name: str) -> None:
	if user_has_unrestricted_support_ticket_catalog(user):
		return
	cust = frappe.db.get_value("Support Ticket", ticket_name, "customer")
	allowed_cust = get_allowed_customers(user)
	if allowed_cust and cust and cust in allowed_cust:
		return
	if user_sees_all_support_records(user):
		if internal_user_may_access_support_ticket(user, ticket_name):
			return
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not allowed_cust:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not cust or cust not in allowed_cust:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _assert_portal_task_access(user: str, task_name: str) -> None:
	if user_has_unrestricted_support_ticket_catalog(user):
		return
	ticket = frappe.db.get_value("Support Task", task_name, "support_ticket")
	if ticket:
		cust = frappe.db.get_value("Support Ticket", ticket, "customer")
		allowed_cust = get_allowed_customers(user)
		if allowed_cust and cust and cust in allowed_cust:
			return
	if user_sees_all_support_records(user):
		if ticket:
			if internal_user_may_access_support_ticket(user, ticket):
				return
		elif frappe.db.get_value("Support Task", task_name, "assigned_to_user") == user:
			return
		elif frappe.db.exists("Support Task Assignee", {"parent": task_name, "user": user}):
			return
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	customers = get_allowed_customers(user)
	if not customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not ticket:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	cust = frappe.db.get_value("Support Ticket", ticket, "customer")
	if not cust or cust not in customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _portal_due_datetime_wire(val):
	"""Return ``(string, YYYY-MM-DD)`` for naive MariaDB datetimes.

	JavaScript ``new Date('YYYY-MM-DD HH:mm:ss').toISOString().slice(0, 10)`` shifts the
	calendar day (UTC vs local). Expose an explicit calendar date for agenda-style clients.
	"""
	if val is None:
		return None, None
	s = str(val).strip()
	if not s:
		return None, None
	if len(s) >= 26 and s[19] == ".":
		s = s[:19]
	cal = None
	if len(s) >= 10 and s[4] == "-" and s[7] == "-":
		cal = s[:10]
	return s, cal


@frappe.whitelist()
def get_portal_ticket(name: str):
	"""Single ticket for the React portal (no desk / web form redirect).

	Always includes ``due_date`` (and ``due_date_calendar``) from Support Ticket. If the DocType has
	``expected_delivery_date`` (e.g. customized site / Desk field), that is fetched and returned too.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	name = (name or "").strip()
	if not name or not frappe.db.exists("Support Ticket", name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, name)
	ticket_meta = frappe.get_meta("Support Ticket")
	# Read from DB so schedule fields are not stripped by Doc field-permission rules for portal users.
	row_fields = [
		"name",
		"subject",
		"status",
		"priority",
		"ticket_type",
		"team",
		"division",
		"customer",
		"customer_name",
		"assigned_to",
		"action_required_from",
		"current_owner_type",
		"modified",
		"opening_date",
		"due_date",
		"waiting_since",
		"description",
		"customer_resolution_deadline",
		"customer_confirmation_required",
		"resolved_on",
		"closed_on",
		"last_customer_reply_on",
		"last_technician_reply_on",
		"resolution_summary",
		"resolution_type",
		"root_cause",
		"google_meet_url",
		"google_meet_created_on",
		"live_support_status",
		"last_meet_notification_on",
	]
	if ticket_meta.has_field("expected_delivery_date"):
		row_fields.insert(row_fields.index("due_date") + 1, "expected_delivery_date")

	row = frappe.db.get_value(
		"Support Ticket",
		name,
		row_fields,
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	desc = row.get("description") or ""
	desc = strip_html(desc).strip() if desc else ""

	def _dt(val):
		return str(val) if val else None

	due_s, due_cal = _portal_due_datetime_wire(row.due_date)

	ticket_assignees = _assignee_users_by_parent("Support Ticket Assignee", [name]).get(name, [])
	tt_label = ""
	if row.ticket_type:
		tt_label = frappe.db.get_value("Support Ticket Type", row.ticket_type, "ticket_type_name") or row.ticket_type

	can_edit_ticket_schedule = user_can_edit_portal_ticket_schedule(user, name)
	internal = user_sees_all_support_records(user)

	res_html = row.get("resolution_summary") or ""
	if res_html:
		res_html = sanitize_html(str(res_html))

	comm_locked = _ticket_communication_locked(row.status)

	out = {
		"name": row.name,
		"subject": row.subject,
		"status": row.status,
		"priority": row.priority or "",
		"ticket_type": row.ticket_type or "",
		"ticket_type_label": tt_label,
		"team": row.team or "",
		"division": row.division or "",
		"customer": row.customer or "",
		"customer_name": row.customer_name or "",
		"assigned_to": row.assigned_to or "",
		"action_required_from": getattr(row, "action_required_from", None) or "",
		"current_owner_type": getattr(row, "current_owner_type", None) or "",
		"assigned_users": ticket_assignees,
		"modified": _dt(row.modified),
		"opening_date": _dt(row.opening_date),
		"due_date": due_s,
		"due_date_calendar": due_cal,
		"waiting_since": _dt(getattr(row, "waiting_since", None)),
		"description": desc,
		"customer_resolution_deadline": _dt(row.customer_resolution_deadline),
		"customer_confirmation_required": int(row.customer_confirmation_required or 0),
		"can_edit_ticket_schedule": bool(can_edit_ticket_schedule),
		"resolved_on": _dt(row.resolved_on),
		"closed_on": _dt(row.closed_on),
		"last_customer_reply_on": _dt(getattr(row, "last_customer_reply_on", None)),
		"last_technician_reply_on": _dt(getattr(row, "last_technician_reply_on", None)),
		"resolution_type": row.resolution_type or "",
		"resolution_summary_html": res_html,
		"communication_locked": comm_locked,
		"google_meet_url": row.google_meet_url or "",
		"google_meet_created_on": _dt(row.google_meet_created_on),
		"live_support_status": row.live_support_status or "Not Started",
		"last_meet_notification_on": _dt(row.last_meet_notification_on),
	}
	if ticket_meta.has_field("expected_delivery_date"):
		out["expected_delivery_date"] = _dt(row.get("expected_delivery_date"))
	if internal:
		out["root_cause"] = (row.root_cause or "").strip() or None
	return out


@frappe.whitelist()
def get_portal_task(name: str):
	"""Single task for the React portal."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	name = (name or "").strip()
	if not name or not frappe.db.exists("Support Task", name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_task_access(user, name)
	# Read from DB so schedule fields (due_date, etc.) are not stripped for Website Users.
	row = frappe.db.get_value(
		"Support Task",
		name,
		[
			"name",
			"subject",
			"status",
			"task_type",
			"support_ticket",
			"ticket_subject",
			"customer",
			"division",
			"project",
			"responsible_side",
			"assigned_to_user",
			"predecessor_task",
			"modified",
			"creation",
			"due_date",
			"planned_start_date",
			"planned_end_date",
			"actual_start_date",
			"actual_end_date",
			"is_delayed",
			"delay_owner",
			"delay_reason",
			"delay_remarks",
			"delay_days",
			"description",
		],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	desc = row.get("description") or ""
	desc = strip_html(desc).strip() if desc else ""

	def _dt(val):
		return str(val) if val else None

	def _num(val):
		if val is None:
			return None
		try:
			return float(val)
		except (TypeError, ValueError):
			return None

	due_s, due_cal = _portal_due_datetime_wire(row.due_date)

	task_assignees = _assignee_users_by_parent("Support Task Assignee", [name]).get(name, [])

	can_edit_task_schedule = user_can_edit_portal_task_schedule(user, name)

	task_comm_locked = False
	if row.support_ticket:
		tst = frappe.db.get_value("Support Ticket", row.support_ticket, "status")
		task_comm_locked = _ticket_communication_locked(tst)
	else:
		task_comm_locked = (row.status or "").strip() in _TERMINAL_TASK_STATUS

	return {
		"name": row.name,
		"subject": row.subject,
		"status": row.status,
		"task_type": row.task_type or "",
		"support_ticket": row.support_ticket or "",
		"ticket_subject": row.ticket_subject or "",
		"customer": row.customer or "",
		"division": row.division or "",
		"project": row.project or "",
		"responsible_side": row.responsible_side or "",
		"assigned_to_user": row.assigned_to_user or "",
		"assigned_users": task_assignees,
		"predecessor_task": row.predecessor_task or "",
		"modified": _dt(row.modified),
		"creation": _dt(row.creation),
		"due_date": due_s,
		"due_date_calendar": due_cal,
		"planned_start_date": _dt(row.planned_start_date),
		"planned_end_date": _dt(row.planned_end_date),
		"actual_start_date": _dt(row.actual_start_date),
		"actual_end_date": _dt(row.actual_end_date),
		"is_delayed": int(row.is_delayed or 0),
		"delay_owner": row.delay_owner or "",
		"delay_reason": row.delay_reason or "",
		"delay_remarks": row.delay_remarks or "",
		"delay_days": _num(row.delay_days),
		"description": desc,
		"communication_locked": bool(task_comm_locked),
		"can_edit_task_schedule": bool(can_edit_task_schedule),
	}


_SUPPORT_TICKET_STATUSES = (
	"Open",
	"Assigned",
	"In Progress",
	"Hold",
	"Waiting for Customer",
	"Waiting for Technician",
	"Reopened",
	"Resolved",
	"Closed",
	"Cancelled",
)
_TERMINAL_TICKET_STATUSES = frozenset({"Resolved", "Closed", "Cancelled"})
# Only after internal work is done: ticket should be waiting on the customer (not Open / In Progress / etc.).
_STATUSES_ELIGIBLE_FOR_CUSTOMER_CONFIRMATION_REQUEST = frozenset(
	{"Waiting for Customer", "Resolved", "In Progress", "Assigned", "Waiting for Technician", "Open"}
)

_SUPPORT_TASK_STATUSES = (
	"Open",
	"In Progress",
	"Waiting for Customer",
	"Waiting for Printechs",
	"Completed",
	"Cancelled",
	"Delayed",
)
_CUSTOMER_VISIBLE_TASK_STATUSES = frozenset(
	{
		"Open",
		"In Progress",
		"Waiting for Customer",
		"Waiting for Printechs",
		"Completed",
	}
)


def _apply_support_ticket_status_via_portal(
	ticket_name: str,
	new_status: str,
	user: str,
	customer_confirmation_html: str | None = None,
) -> None:
	"""Set Support Ticket status (with workflow routing fields) and append a portal system comment.

	Must keep ``action_required_from`` / ``current_owner_type`` aligned with ``status`` or
	:func:`validate_workflow_consistency` rejects the save.

	Caller must enforce permissions. Skips when ``new_status`` already matches ``status``.
	"""
	from printechs_support.printechs_support_system.api.ticket_workflow import (
		derive_workflow_routing_for_status,
		sync_waiting_side_fields,
	)

	new_status = (new_status or "").strip()
	if not new_status:
		return

	doc = frappe.get_doc("Support Ticket", ticket_name)
	old = doc.status or ""
	if old == new_status:
		return

	ar, cot = derive_workflow_routing_for_status(new_status)
	doc.status = new_status
	doc.action_required_from = ar
	doc.current_owner_type = cot
	if new_status == "Resolved" and not doc.resolved_on:
		doc.resolved_on = now_datetime()
	if new_status == "Closed" and not doc.closed_on:
		doc.closed_on = now_datetime()
	if new_status in _TERMINAL_TICKET_STATUSES:
		doc.customer_resolution_deadline = None
		doc.customer_confirmation_required = 0

	sync_waiting_side_fields(doc)
	doc.flags.workflow_transition = True
	try:
		if customer_confirmation_html:
			doc.append(
				"comments",
				{
					"comment_type": "Customer Reply",
					"comment_by": user,
					"comment_on": frappe.utils.now(),
					"is_customer_visible": 1,
					"content": customer_confirmation_html,
				},
			)
		doc.append(
			"comments",
			{
				"comment_type": "System Update",
				"comment_by": user,
				"comment_on": frappe.utils.now(),
				"is_customer_visible": 1,
				"content": sanitize_html(
					f"<p><strong>Status</strong> updated from <em>{html_escape(old)}</em> to <em>{html_escape(new_status)}</em></p>"
				),
			},
		)
		doc.save(ignore_permissions=True)
	finally:
		doc.flags.workflow_transition = False


def _get_portal_doc(doctype: str, name: str):
	"""Load document after row-level portal check; ignore DocType read rules for Website Users."""
	prev = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		return frappe.get_doc(doctype, name)
	finally:
		frappe.flags.ignore_permissions = prev


def _clean_portal_comment_html(content: str) -> str:
	if not content or not str(content).strip():
		frappe.throw(_("Comment is required"), frappe.ValidationError)
	out = sanitize_html(str(content).strip())
	if not out or not strip_html(out).strip():
		frappe.throw(_("Comment is required"), frappe.ValidationError)
	return out


def _validate_portal_comment_attachment(file_name: str, ticket_name: str) -> None:
	"""Ensure File row exists and is attached to this Support Ticket (from portal_upload_ticket_file)."""
	file_name = (file_name or "").strip()
	if not file_name:
		return
	row = frappe.db.get_value(
		"File",
		file_name,
		["name", "attached_to_doctype", "attached_to_name", "is_folder"],
		as_dict=True,
	)
	if not row or row.get("is_folder"):
		frappe.throw(_("Invalid attachment"), frappe.ValidationError)
	if row.get("attached_to_doctype") != "Support Ticket" or row.get("attached_to_name") != ticket_name:
		frappe.throw(_("Invalid attachment"), frappe.ValidationError)


def _validate_portal_task_comment_attachment(file_name: str, task_name: str) -> None:
	"""Ensure File row exists and is attached to this Support Task (from portal_upload_task_file)."""
	file_name = (file_name or "").strip()
	if not file_name:
		return
	row = frappe.db.get_value(
		"File",
		file_name,
		["name", "attached_to_doctype", "attached_to_name", "is_folder"],
		as_dict=True,
	)
	if not row or row.get("is_folder"):
		frappe.throw(_("Invalid attachment"), frappe.ValidationError)
	if row.get("attached_to_doctype") != "Support Task" or row.get("attached_to_name") != task_name:
		frappe.throw(_("Invalid attachment"), frappe.ValidationError)


def _serialize_comment_row(row: dict, **extras) -> dict:
	by = row.get("comment_by") or ""
	full = frappe.db.get_value("User", by, "full_name") if by else ""
	author_is_internal = user_sees_all_support_records(by) if by else False
	att = row.get("attachment")
	att_url = None
	if att:
		att_url = frappe.db.get_value("File", att, "file_url")
		if att_url and not str(att_url).startswith("http"):
			att_url = get_url(att_url)
	content = row.get("content") or ""
	content = sanitize_html(content) if content else ""
	reply_to = (row.get("in_reply_to") or "").strip() or None
	comment_type = row.get("comment_type")
	display_comment_type = comment_type
	visible = int(row.get("is_customer_visible") or 0)
	if visible and (comment_type or "").strip() in ("", "Comment", "Reply", "Customer Reply"):
		display_comment_type = "Technician" if author_is_internal else "Customer"
	out = {
		"name": row.get("name"),
		"comment_type": comment_type,
		"display_comment_type": display_comment_type,
		"comment_by": by,
		"author_name": full or by,
		"author_is_internal": author_is_internal,
		"comment_on": str(row.get("comment_on")) if row.get("comment_on") else None,
		"is_customer_visible": visible,
		"content": content,
		"in_reply_to": reply_to,
		"attachment": att,
		"attachment_url": att_url,
		"internal_only": not int(row.get("is_customer_visible") or 0),
	}
	out.update(extras)
	return out


def _portal_comment_sort_key(row: dict):
	"""Stable chronological sort for merged ticket + task threads."""
	co = row.get("comment_on")
	try:
		d = get_datetime(co) if co else None
	except Exception:
		d = None
	ts = d.timestamp() if d else 0.0
	return (ts, row.get("name") or "")


@frappe.whitelist()
def get_portal_ticket_comments(ticket_name: str):
	"""Comments on the ticket plus comments on linked Support Tasks (merged, chronological).

	Task rows include ``thread_scope``, ``task_name``, and ``task_subject`` so the portal can label them.
	Reply targets remain within each document type (ticket replies use Support Ticket Comment names only).
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, ticket_name)

	internal = user_sees_all_support_records(user)
	filters = {
		"parent": ticket_name,
		"parenttype": "Support Ticket",
		"parentfield": "comments",
	}
	if not internal:
		filters["is_customer_visible"] = 1

	rows = frappe.get_all(
		"Support Ticket Comment",
		filters=filters,
		fields=[
			"name",
			"comment_type",
			"comment_by",
			"comment_on",
			"is_customer_visible",
			"content",
			"in_reply_to",
			"attachment",
		],
		order_by="comment_on asc, creation asc",
		limit_page_length=500,
	)

	out = [_serialize_comment_row(r, thread_scope="ticket") for r in rows]

	task_names = frappe.get_all(
		"Support Task",
		filters={"support_ticket": ticket_name},
		pluck="name",
		order_by="creation asc",
		limit_page_length=500,
	)
	for tn in task_names:
		subject = frappe.db.get_value("Support Task", tn, "subject") or tn
		tf = {
			"parent": tn,
			"parenttype": "Support Task",
			"parentfield": "comments",
		}
		if not internal:
			tf["is_customer_visible"] = 1
		task_rows = frappe.get_all(
			"Support Task Comment",
			filters=tf,
			fields=[
				"name",
				"comment_type",
				"comment_by",
				"comment_on",
				"is_customer_visible",
				"content",
				"in_reply_to",
				"attachment",
			],
			order_by="comment_on asc, creation asc",
			limit_page_length=500,
		)
		for r in task_rows:
			out.append(
				_serialize_comment_row(
					r,
					thread_scope="task",
					task_name=tn,
					task_subject=subject,
				)
			)

	out.sort(key=_portal_comment_sort_key)
	return out


@frappe.whitelist()
def get_portal_ticket_desk_history(ticket_name: str, limit: int = 50):
	"""Field-level history from Frappe ``Version`` (edits saved from Desk and other full document saves).

	Internal portal users only — same source as **Menu → Versions** on the ticket form.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, ticket_name)
	if not user_sees_all_support_records(user):
		return {"entries": []}

	limit = min(max(cint(limit), 1), 100)
	ref_meta = frappe.get_meta("Support Ticket")
	vrows = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Support Ticket", "docname": ticket_name},
		fields=["name", "owner", "creation", "data"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	entries = []
	for r in vrows:
		try:
			row = format_version_row_for_portal(r, ref_meta)
			if row.get("changes"):
				entries.append(row)
		except Exception:
			continue
	entries.reverse()
	return {"entries": entries}


@frappe.whitelist()
def add_portal_ticket_comment(
	ticket_name: str,
	content: str,
	is_internal_note=None,
	in_reply_to=None,
	attachment=None,
	set_status=None,
	reply_mode=None,
	technician_reply_effect=None,
):
	"""Append a Support Ticket Comment row. Internal notes only for internal portal users.

	``in_reply_to``: optional name of another comment row on the same ticket (threaded reply).
	``attachment``: optional File name (from :func:`portal_upload_ticket_file`) linked to this ticket.
	``set_status``: optional target Support Ticket status (internal users only), applied after the comment.
	``reply_mode``: for **customer-visible** replies while status is **Waiting for Customer** (see handoff below):
	  - omit or ``provide_information`` — run smart workflow so status becomes **Waiting for Technician**.
	  - ``acknowledgement_only`` — thread message only (no handoff); use for courtesy / “I'll check” notes.

	**Handoff who-qualifies:** same as desk “customer” workflow actions—anyone who may represent the
	ticket’s customer (typical portal user, or an internal user also linked to that customer), not
	“non-internal sessions only” (so mixed staff/customer roles are not stuck on this status).

	``technician_reply_effect`` (internal users, **customer-visible** reply only; ignored if
	``set_status`` is passed): drives smart workflow before the comment is saved —
	``normal_reply`` → work update (:func:`ticket_workflow.technician_send_work_update`), not applied
	when status is already *Waiting for Customer* (comment-only; use expect-customer instead);
	``expect_customer_response`` → *Waiting for Customer*
	(:func:`ticket_workflow.technician_request_customer_input`).
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, ticket_name)
	_assert_ticket_communication_allowed(ticket_name)

	internal = user_sees_all_support_records(user)
	want_internal = bool(cint(is_internal_note))
	if want_internal and not internal:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if internal and want_internal:
		comment_type = "Internal Note"
		visible = 0
	else:
		comment_type = "Customer Reply"
		visible = 1

	reply_to_name = (in_reply_to or "").strip()
	reply_row = None
	if reply_to_name:
		reply_row = frappe.db.get_value(
			"Support Ticket Comment",
			{"name": reply_to_name, "parent": ticket_name, "parenttype": "Support Ticket"},
			["name", "is_customer_visible"],
			as_dict=True,
		)
		if not reply_row:
			frappe.throw(_("Invalid reply target"), frappe.ValidationError)
		if not internal and not int(reply_row.get("is_customer_visible") or 0):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	att_name = (attachment or "").strip()
	if att_name:
		_validate_portal_comment_attachment(att_name, ticket_name)

	has_text = bool(content and str(content).strip())
	if att_name and not has_text:
		safe = "<p>Shared an attachment.</p>"
	else:
		safe = _clean_portal_comment_html(content)

	ss_early = (set_status or "").strip()
	skip_customer_wfc_for_staff_intent = False
	staff_reply_intent_value = ""

	# Internal staff: optional smart workflow when posting a customer-visible reply (portal intent).
	if internal and visible and not ss_early:
		tr = (technician_reply_effect or "").strip().lower().replace("-", "_")
		if tr in ("normal_reply", "expect_customer_response"):
			from printechs_support.printechs_support_system.api import ticket_workflow as tw

			skip_customer_wfc_for_staff_intent = True
			cur_for_staff = (frappe.db.get_value("Support Ticket", ticket_name, "status") or "").strip()
			if cur_for_staff not in ("Closed", "Cancelled"):
				plain_staff = (strip_html(safe) or "").strip() or (
					_("Shared an attachment.") if att_name else _("(message)")
				)
				if tr == "expect_customer_response":
					staff_reply_intent_value = "Expect Customer Response"
					tw.technician_request_customer_input(ticket_name, plain_staff, user=user)
				elif tr == "normal_reply":
					staff_reply_intent_value = "Normal Reply"
					if cur_for_staff != "Waiting for Customer":
						tw.technician_send_work_update(ticket_name, plain_staff, user=user)
					# Waiting for Customer + “normal”: do not call work_update (would break routing).

	# While “Waiting for Customer”, a **customer-visible** reply can hand the ticket back to support.
	# Use the same “is this user the customer for this ticket?” rule as desk workflow (not ``not internal``),
	# so staff with both internal + customer roles, and agreement-linked contacts, are not stuck.
	if visible and not skip_customer_wfc_for_staff_intent:
		cur_st = frappe.db.get_value("Support Ticket", ticket_name, "status")
		if (cur_st or "").strip() == "Waiting for Customer":
			from printechs_support.printechs_support_system.api.ticket_workflow import (
				_assert_customer,
				customer_informational_reply,
				customer_provide_requested_information,
			)

			doc_gate = frappe.get_cached_doc("Support Ticket", ticket_name)
			try:
				_assert_customer(doc_gate, user)
			except (frappe.PermissionError, frappe.ValidationError):
				pass
			else:
				mode = (reply_mode or "").strip().lower().replace("-", "_")
				plain = (strip_html(safe) or "").strip() or (
					_("Shared an attachment.") if att_name else _("(message)")
				)
				if mode in ("acknowledgement_only", "acknowledgement", "informational"):
					customer_informational_reply(ticket_name, plain, user=user)
				else:
					customer_provide_requested_information(ticket_name, plain, user=user)

	doc = _get_portal_doc("Support Ticket", ticket_name)
	row_data = {
		"comment_type": comment_type,
		"comment_by": user,
		"comment_on": frappe.utils.now(),
		"is_customer_visible": visible,
		"content": safe,
	}
	if staff_reply_intent_value:
		row_data["staff_reply_intent"] = staff_reply_intent_value
	if reply_to_name and reply_row:
		row_data["in_reply_to"] = reply_to_name
	if att_name:
		row_data["attachment"] = att_name
	doc.append(
		"comments",
		row_data,
	)
	# Child-table diff is often missing in on_update's get_doc_before_save(); notify after save instead.
	doc.flags.skip_comment_notification_hook = True
	doc.save(ignore_permissions=True)

	frappe.db.set_value(
		"Support Ticket",
		ticket_name,
		"last_customer_update_on" if visible else "last_internal_update_on",
		frappe.utils.now(),
	)

	from printechs_support.printechs_support_system.api.ticket_comment_emails import notify_ticket_comment

	try:
		notify_ticket_comment(
			ticket_name,
			comment_type=comment_type,
			comment_by=user,
			content_html=safe,
			is_internal_note=not bool(visible),
			author_is_internal=internal,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "portal add_portal_ticket_comment notify")

	ss = ss_early or (set_status or "").strip()
	if ss:
		if not internal:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if ss not in _SUPPORT_TICKET_STATUSES:
			frappe.throw(_("Invalid status"), frappe.ValidationError)
		_apply_support_ticket_status_via_portal(ticket_name, ss, user)

	cur_status = frappe.db.get_value("Support Ticket", ticket_name, "status")
	return {"ok": True, "ticket_status": cur_status}


@frappe.whitelist()
def portal_ticket_workflow_action(
	action: str,
	ticket_name: str,
	message: str | None = None,
	technician_user: str | None = None,
	due_date=None,
	note: str | None = None,
	reopen_from_resolved: int | None = None,
	reason: str | None = None,
):
	"""Execute a structured workflow step from the portal (dispatches :mod:`ticket_workflow`)."""
	from printechs_support.printechs_support_system.api import ticket_workflow as tw

	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	action = (action or "").strip()
	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)

	internal = user_sees_all_support_records(user)

	def _need_msg() -> str:
		m = (message or "").strip()
		if not m:
			frappe.throw(_("Message is required."), frappe.ValidationError)
		return m

	if action == "assign_ticket":
		if not internal:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		tu = (technician_user or "").strip()
		if not tu:
			frappe.throw(_("Technician user is required."), frappe.ValidationError)
		return tw.assign_ticket(ticket_name, tu, due_date=due_date, note=note or message)

	if action == "technician_ack":
		return tw.technician_send_acknowledgement(ticket_name, _need_msg())

	if action == "start_work":
		return tw.technician_start_work(ticket_name, message=message)

	if action == "request_customer_input":
		return tw.technician_request_customer_input(ticket_name, _need_msg())

	if action == "customer_ack":
		return tw.customer_acknowledgement(ticket_name, _need_msg())

	if action == "customer_info_reply":
		return tw.customer_informational_reply(ticket_name, _need_msg())

	if action == "customer_provide_info":
		return tw.customer_provide_requested_information(ticket_name, _need_msg())

	if action == "customer_followup":
		return tw.customer_followup_question(
			ticket_name,
			_need_msg(),
			reopen_from_resolved=bool(int(reopen_from_resolved or 0)),
		)

	if action == "resume_work":
		return tw.technician_resume_after_customer_reply(ticket_name, message=message)

	if action == "work_update":
		return tw.technician_send_work_update(ticket_name, _need_msg())

	if action == "send_resolution":
		return tw.technician_send_resolution(ticket_name, _need_msg())

	if action == "customer_confirm":
		return tw.customer_confirm_resolved(ticket_name, message=message)

	if action == "customer_reopen":
		return tw.customer_reopen_issue(ticket_name, _need_msg())

	if action == "internal_note":
		return tw.technician_internal_note(ticket_name, _need_msg())

	if action == "manager_close":
		return tw.manager_close_ticket(ticket_name, message=message)

	if action == "cancel_ticket":
		if not internal:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return tw.cancel_ticket(ticket_name, reason=reason or message)

	frappe.throw(_("Unknown workflow action."), frappe.ValidationError)


@frappe.whitelist()
def get_portal_ticket_workflow_log(ticket_name: str):
	"""Timeline rows from Support Ticket Workflow Log (hides internal rows from customers)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)
	internal = user_sees_all_support_records(user)
	doc = frappe.get_doc("Support Ticket", ticket_name)
	entries = []
	for row in doc.workflow_log or []:
		if int(row.is_internal or 0) and not internal:
			continue
		entries.append(
			{
				"name": row.name,
				"posted_by": row.posted_by,
				"posted_by_role_type": row.posted_by_role_type,
				"reply_type": row.reply_type,
				"subject": row.subject or "",
				"message": row.message or "",
				"previous_status": row.previous_status or "",
				"new_status": row.new_status or "",
				"previous_action_required_from": row.previous_action_required_from or "",
				"new_action_required_from": row.new_action_required_from or "",
				"created_on": str(row.created_on) if row.created_on else None,
				"attachment": row.attachment or "",
			}
		)
	return {"entries": entries}


@frappe.whitelist()
def get_portal_task_comments(task_name: str):
	"""Threaded comments on a Support Task (child table). Customer portal users only see customer-visible rows."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (task_name or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_task_access(user, task_name)

	internal = user_sees_all_support_records(user)
	filters = {
		"parent": task_name,
		"parenttype": "Support Task",
		"parentfield": "comments",
	}
	if not internal:
		filters["is_customer_visible"] = 1

	rows = frappe.get_all(
		"Support Task Comment",
		filters=filters,
		fields=[
			"name",
			"comment_type",
			"comment_by",
			"comment_on",
			"is_customer_visible",
			"content",
			"in_reply_to",
			"attachment",
		],
		order_by="comment_on asc, creation asc",
		limit_page_length=500,
	)

	return [_serialize_comment_row(r) for r in rows]


@frappe.whitelist()
def add_portal_task_comment(
	task_name: str,
	content: str,
	is_internal_note=None,
	in_reply_to=None,
	attachment=None,
	set_status=None,
):
	"""Append a Support Task Comment row. Same behaviour as ticket comments (internal notes, replies, attachments).

	``set_status``: optional Support Task status (internal users only), applied after the comment.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (task_name or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_task_access(user, task_name)
	_assert_task_communication_allowed(task_name)

	internal = user_sees_all_support_records(user)
	want_internal = bool(cint(is_internal_note))
	if want_internal and not internal:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if internal and want_internal:
		comment_type = "Internal Note"
		visible = 0
	else:
		comment_type = "Customer Reply"
		visible = 1

	reply_to_name = (in_reply_to or "").strip()
	reply_row = None
	if reply_to_name:
		reply_row = frappe.db.get_value(
			"Support Task Comment",
			{"name": reply_to_name, "parent": task_name, "parenttype": "Support Task"},
			["name", "is_customer_visible"],
			as_dict=True,
		)
		if not reply_row:
			frappe.throw(_("Invalid reply target"), frappe.ValidationError)
		if not internal and not int(reply_row.get("is_customer_visible") or 0):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	att_name = (attachment or "").strip()
	if att_name:
		_validate_portal_task_comment_attachment(att_name, task_name)

	has_text = bool(content and str(content).strip())
	if att_name and not has_text:
		safe = "<p>Shared an attachment.</p>"
	else:
		safe = _clean_portal_comment_html(content)

	doc = _get_portal_doc("Support Task", task_name)
	row_data = {
		"comment_type": comment_type,
		"comment_by": user,
		"comment_on": frappe.utils.now(),
		"is_customer_visible": visible,
		"content": safe,
	}
	if reply_to_name and reply_row:
		row_data["in_reply_to"] = reply_to_name
	if att_name:
		row_data["attachment"] = att_name
	doc.append(
		"comments",
		row_data,
	)
	doc.save(ignore_permissions=True)

	if visible and internal and doc.support_ticket:
		from printechs_support.printechs_support_system.api.ticket_comment_emails import notify_ticket_comment

		try:
			notify_ticket_comment(
				doc.support_ticket,
				comment_type=comment_type,
				comment_by=user,
				content_html=safe,
				is_internal_note=False,
				author_is_internal=True,
				notify_team=False,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "portal add_portal_task_comment notify")

	ts = (set_status or "").strip()
	if ts:
		if not internal:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if ts not in _SUPPORT_TASK_STATUSES:
			frappe.throw(_("Invalid status"), frappe.ValidationError)
		prev = frappe.flags.ignore_permissions
		frappe.flags.ignore_permissions = True
		try:
			frappe.db.set_value("Support Task", task_name, "status", ts)
		finally:
			frappe.flags.ignore_permissions = prev

	cur_task = frappe.db.get_value("Support Task", task_name, "status")
	return {"ok": True, "task_status": cur_task}


@frappe.whitelist()
def update_portal_ticket(
	ticket_name: str,
	subject: str | None = None,
	description: str | None = None,
	priority: str | None = None,
):
	"""Update editable fields on a Support Ticket from the portal.

	Internal users may change subject, description, and priority. Portal customers may change
	description only (use status / due-date RPCs for other changes).

	Call with ``ticket_name`` only to verify the method exists (capability probe).
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, ticket_name)
	internal = user_sees_all_support_records(user)

	has_subject = subject is not None
	has_description = description is not None
	has_priority = priority is not None

	if not (has_subject or has_description or has_priority):
		return {"ok": True}

	if not internal and (has_subject or has_priority):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if has_subject or has_description:
		_assert_ticket_communication_allowed(ticket_name)

	doc = frappe.get_doc("Support Ticket", ticket_name)
	changed = False

	if has_subject:
		s = (subject or "").strip()
		if not s:
			frappe.throw(_("Subject is required"), frappe.ValidationError)
		if doc.subject != s:
			doc.subject = s
			changed = True

	if has_description:
		raw = str(description).strip() if description is not None else ""
		desc = sanitize_html(raw) if raw else ""
		if not strip_html(desc).strip():
			desc = ""
		if doc.description != desc:
			doc.description = desc
			changed = True

	if has_priority:
		p = (priority or "").strip()
		if p not in _VALID_CREATE_PRIORITIES:
			frappe.throw(_("Invalid priority"), frappe.ValidationError)
		if doc.priority != p:
			doc.priority = p
			doc.flags.priority_from_portal = 1
			changed = True

	if changed:
		doc.save(ignore_permissions=True)

	return {
		"ok": True,
		"name": doc.name,
		"subject": doc.subject,
		"status": doc.status,
		"priority": doc.priority,
	}


@frappe.whitelist()
def update_portal_task(
	task_name: str,
	subject: str | None = None,
	description: str | None = None,
):
	"""Update editable fields on a Support Task from the portal.

	Internal users may change subject and description. Portal customers (tasks linked to a ticket they
	can see) may change **description** only. When the linked ticket is resolved/closed, communication
	is locked (same as ticket comments). Standalone internal tasks (no ticket): internal team only.

	Call with ``task_name`` only to verify the method exists (capability probe).
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (task_name or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_task_access(user, task_name)
	internal = user_sees_all_support_records(user)

	has_subject = subject is not None
	has_description = description is not None

	if not (has_subject or has_description):
		return {"ok": True}

	if not internal and has_subject:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = frappe.db.get_value("Support Task", task_name, "support_ticket")
	if ticket_name and (has_subject or has_description):
		_assert_ticket_communication_allowed(ticket_name)
	elif not ticket_name and not internal:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	doc = frappe.get_doc("Support Task", task_name)
	changed = False

	if has_subject:
		s = (subject or "").strip()
		if not s:
			frappe.throw(_("Subject is required"), frappe.ValidationError)
		if doc.subject != s:
			doc.subject = s
			changed = True

	if has_description:
		raw = str(description).strip() if description is not None else ""
		if raw:
			if "<" in raw:
				desc_val = sanitize_html(raw)
				if not strip_html(desc_val).strip():
					desc_val = ""
			else:
				desc_val = f"<p>{html_escape(raw).replace(chr(10), '<br>')}</p>"
		else:
			desc_val = ""
		if doc.description != desc_val:
			doc.description = desc_val
			changed = True

	if changed:
		doc.save(ignore_permissions=True)

	return {
		"ok": True,
		"name": doc.name,
		"subject": doc.subject,
		"status": doc.status,
	}


@frappe.whitelist()
def update_portal_ticket_status(ticket_name: str, status: str, confirmation_comment: str | None = None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	status = (status or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	if status not in _SUPPORT_TICKET_STATUSES:
		frappe.throw(_("Invalid status"), frappe.ValidationError)

	_assert_portal_ticket_access(user, ticket_name)

	internal = user_sees_all_support_records(user)
	customer_confirmation_html = None
	if not internal:
		if status != "Resolved":
			frappe.throw(
				_("Customers can only confirm resolution by setting status to Resolved."),
				frappe.PermissionError,
			)
		cur = frappe.db.get_value("Support Ticket", ticket_name, "status")
		if cur in _TERMINAL_TICKET_STATUSES:
			frappe.throw(_("This ticket is already closed."), frappe.ValidationError)
		if cur != "Waiting for Customer":
			deadline = frappe.db.get_value("Support Ticket", ticket_name, "customer_resolution_deadline")
			if not deadline:
				frappe.throw(
					_("Your support team has not opened a confirmation window for this ticket yet."),
					frappe.PermissionError,
				)
			if now_datetime() > get_datetime(deadline):
				frappe.throw(_("The confirmation period has ended."), frappe.ValidationError)
		if (confirmation_comment or "").strip():
			customer_confirmation_html = _clean_portal_comment_html(confirmation_comment)

	doc = _get_portal_doc("Support Ticket", ticket_name)
	old = doc.status
	if old == status:
		return {"ok": True, "status": status}

	# Workflow validates transitions by user role (see get_transitions). Portal users often lack
	# the workflow "allowed" role even when the API permits the target status. Set status via DB
	# (no workflow), then save only the new comment row so validate_workflow sees no transition.
	_apply_support_ticket_status_via_portal(ticket_name, status, user, customer_confirmation_html)
	return {"ok": True, "status": status}


@frappe.whitelist()
def update_portal_task_status(task_name: str, status: str):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (task_name or "").strip()
	status = (status or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	if status not in _SUPPORT_TASK_STATUSES:
		frappe.throw(_("Invalid status"), frappe.ValidationError)

	_assert_portal_task_access(user, task_name)

	internal = user_sees_all_support_records(user)
	if not internal and status not in _CUSTOMER_VISIBLE_TASK_STATUSES:
		frappe.throw(_("This status is not allowed from the portal"), frappe.PermissionError)

	prev = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		frappe.db.set_value("Support Task", task_name, "status", status)
	finally:
		frappe.flags.ignore_permissions = prev
	return {"ok": True, "status": status}


@frappe.whitelist()
def update_portal_task_due_date(task_name: str, due_date: str | None = None):
	"""Set Support Task due date (internal users or task assignees). Send empty ``due_date`` to clear."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (task_name or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_task_access(user, task_name)
	if not user_can_edit_portal_task_schedule(user, task_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	raw = (due_date or "").strip()
	prev = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		doc = frappe.get_doc("Support Task", task_name)
		if not raw:
			doc.due_date = None
		else:
			try:
				doc.due_date = get_datetime(raw)
			except Exception:
				frappe.throw(_("Invalid due date"), frappe.ValidationError)
		doc.flags.ignore_permissions = True
		doc.save()
		out = doc.due_date
		out_s, out_cal = _portal_due_datetime_wire(out)
		return {"ok": True, "due_date": out_s, "due_date_calendar": out_cal}
	finally:
		frappe.flags.ignore_permissions = prev


@frappe.whitelist()
def update_portal_ticket_due_date(ticket_name: str, due_date: str | None = None):
	"""Set Support Ticket due date (internal users or ticket assignees). Pushes to all tasks. Empty clears.

	Uses Document.save() so Version history records ``due_date`` (audit / reports).
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)
	if not user_can_edit_portal_ticket_schedule(user, ticket_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	raw = (due_date or "").strip()
	prev = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		doc = frappe.get_doc("Support Ticket", ticket_name)
		if not raw:
			doc.due_date = None
		else:
			try:
				doc.due_date = get_datetime(raw)
			except Exception:
				frappe.throw(_("Invalid due date"), frappe.ValidationError)
		doc.flags.ignore_permissions = True
		doc.save()
		out = doc.due_date
		out_s, out_cal = _portal_due_datetime_wire(out)
		return {"ok": True, "due_date": out_s, "due_date_calendar": out_cal}
	finally:
		frappe.flags.ignore_permissions = prev


def _parse_assignee_user_list(assignees):
	"""JSON array string or list of User names; empty list clears assignees."""
	if assignees is None:
		return None
	if isinstance(assignees, list):
		return [str(x).strip() for x in assignees if str(x).strip()]
	s = (assignees or "").strip()
	if not s or s == "null":
		return []
	try:
		parsed = frappe.parse_json(s)
	except Exception:
		parsed = None
	if isinstance(parsed, list):
		return [str(x).strip() for x in parsed if str(x).strip()]
	return [x.strip() for x in s.split(",") if x.strip()]


@frappe.whitelist()
def update_portal_ticket_assignment(ticket_name: str, team: str | None = None, assignees=None):
	"""Set team and/or ticket assignees (internal). ``assignees``: JSON list of User ids, first = primary."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_sees_all_support_records(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)

	doc = frappe.get_doc("Support Ticket", ticket_name)
	changed = False
	if team is not None:
		tm = (team or "").strip()
		if tm and not frappe.db.exists("Support Team", tm):
			frappe.throw(_("Invalid team"), frappe.ValidationError)
		doc.team = tm or None
		changed = True

	parsed = _parse_assignee_user_list(assignees)
	if parsed is not None:
		doc.ticket_assignees = []
		doc.assigned_to = None
		seen = set()
		idx = 0
		for uid in parsed:
			if uid in seen:
				continue
			if not frappe.db.exists("User", uid):
				frappe.throw(_("Invalid user: {0}").format(uid), frappe.ValidationError)
			seen.add(uid)
			doc.append("ticket_assignees", {"user": uid, "is_primary": 1 if idx == 0 else 0})
			idx += 1
		changed = True

	if not changed:
		users = _assignee_users_by_parent("Support Ticket Assignee", [ticket_name]).get(ticket_name, [])
		return {
			"ok": True,
			"team": doc.team or "",
			"assigned_to": doc.assigned_to or "",
			"assigned_users": users,
			"status": doc.status or "",
		}

	doc.save(ignore_permissions=True)
	users = _assignee_users_by_parent("Support Ticket Assignee", [ticket_name]).get(ticket_name, [])
	return {
		"ok": True,
		"team": doc.team or "",
		"assigned_to": doc.assigned_to or "",
		"assigned_users": users,
		"status": doc.status or "",
	}


@frappe.whitelist()
def update_portal_task_assignment(task_name: str, assignees=None):
	"""Set task assignees (internal). ``assignees``: JSON list of User ids, first = primary."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_sees_all_support_records(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (task_name or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_task_access(user, task_name)

	doc = frappe.get_doc("Support Task", task_name)
	parsed = _parse_assignee_user_list(assignees)
	if parsed is None:
		users = _assignee_users_by_parent("Support Task Assignee", [task_name]).get(task_name, [])
		return {
			"ok": True,
			"assigned_to_user": doc.assigned_to_user or "",
			"assigned_users": users,
		}

	doc.task_assignees = []
	doc.assigned_to_user = None
	seen = set()
	idx = 0
	for uid in parsed:
		if uid in seen:
			continue
		if not frappe.db.exists("User", uid):
			frappe.throw(_("Invalid user: {0}").format(uid), frappe.ValidationError)
		seen.add(uid)
		doc.append("task_assignees", {"user": uid, "is_primary": 1 if idx == 0 else 0})
		idx += 1

	doc.save(ignore_permissions=True)
	users = _assignee_users_by_parent("Support Task Assignee", [task_name]).get(task_name, [])
	return {"ok": True, "assigned_to_user": doc.assigned_to_user or "", "assigned_users": users}


def _list_attached_files(doctype: str, name: str) -> list[dict]:
	files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": doctype, "attached_to_name": name},
		fields=["name", "file_name", "file_url", "file_size", "creation", "owner", "is_private"],
		order_by="creation desc",
		limit_page_length=200,
	)
	out = []
	for f in files:
		url = f.file_url or ""
		if url and not url.startswith("http"):
			url = get_url(url)
		out.append(
			{
				"name": f.name,
				"file_name": f.file_name,
				"file_url": url,
				"file_size": f.file_size,
				"creation": str(f.creation) if f.creation else None,
				"owner": f.owner,
				"is_private": int(f.is_private or 0),
			}
		)
	return out


@frappe.whitelist()
def get_portal_ticket_files(ticket_name: str):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)
	return _list_attached_files("Support Ticket", ticket_name)


@frappe.whitelist()
def get_portal_task_files(task_name: str):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	task_name = (task_name or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_task_access(user, task_name)
	return _list_attached_files("Support Task", task_name)


@frappe.whitelist()
def portal_upload_ticket_file():
	"""Multipart upload: field ``file``, form field ``ticket_name``."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (frappe.form_dict.get("ticket_name") or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)
	_assert_ticket_communication_allowed(ticket_name)

	if not frappe.request or not frappe.request.files:
		frappe.throw(_("No file"), frappe.ValidationError)

	f = frappe.request.files.get("file")
	if not f:
		frappe.throw(_("No file"), frappe.ValidationError)

	content = f.read()
	if not content:
		frappe.throw(_("Empty file"), frappe.ValidationError)

	fname = secure_filename(f.filename or "upload")
	if not fname:
		fname = "upload"

	prev = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		out = save_file(fname, content, "Support Ticket", ticket_name, is_private=0)
	finally:
		frappe.flags.ignore_permissions = prev
	url = out.file_url or ""
	if url and not url.startswith("http"):
		url = get_url(url)
	return {"ok": True, "name": out.name, "file_name": out.file_name, "file_url": url}


@frappe.whitelist()
def portal_upload_task_file():
	"""Multipart upload: field ``file``, form field ``task_name``."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	task_name = (frappe.form_dict.get("task_name") or "").strip()
	if not task_name or not frappe.db.exists("Support Task", task_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_task_access(user, task_name)
	_assert_task_communication_allowed(task_name)

	if not frappe.request or not frappe.request.files:
		frappe.throw(_("No file"), frappe.ValidationError)

	f = frappe.request.files.get("file")
	if not f:
		frappe.throw(_("No file"), frappe.ValidationError)

	content = f.read()
	if not content:
		frappe.throw(_("Empty file"), frappe.ValidationError)

	fname = secure_filename(f.filename or "upload")
	if not fname:
		fname = "upload"

	prev = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		out = save_file(fname, content, "Support Task", task_name, is_private=0)
	finally:
		frappe.flags.ignore_permissions = prev
	url = out.file_url or ""
	if url and not url.startswith("http"):
		url = get_url(url)
	return {"ok": True, "name": out.name, "file_name": out.file_name, "file_url": url}


@frappe.whitelist()
def get_portal_ticket_status_options(ticket_name: str | None = None):
	"""Allowed ticket status values for the current user (portal).

	Customers see ``Resolved`` when the ticket is waiting for their confirmation, or when a technician
	has started a confirmation window (``customer_resolution_deadline``) that is still active.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	internal = user_sees_all_support_records(user)
	if internal:
		return {"options": list(_SUPPORT_TICKET_STATUSES)}
	tn = (ticket_name or "").strip()
	if not tn:
		return {"options": []}
	if not frappe.db.exists("Support Ticket", tn):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, tn)
	st = frappe.db.get_value("Support Ticket", tn, "status")
	if st in _TERMINAL_TICKET_STATUSES:
		return {"options": []}
	if st == "Waiting for Customer":
		return {"options": ["Resolved"]}
	deadline = frappe.db.get_value("Support Ticket", tn, "customer_resolution_deadline")
	if not deadline:
		return {"options": []}
	if now_datetime() > get_datetime(deadline):
		return {"options": []}
	return {"options": ["Resolved"]}


@frappe.whitelist()
def mark_ticket_awaiting_customer_resolution(ticket_name: str, hours: int = 24):
	"""Internal only: open a window for the customer to confirm Resolved; auto-resolve after ``hours``."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_sees_all_support_records(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	_assert_portal_ticket_access(user, ticket_name)

	st = frappe.db.get_value("Support Ticket", ticket_name, "status")
	if st not in _STATUSES_ELIGIBLE_FOR_CUSTOMER_CONFIRMATION_REQUEST:
		frappe.throw(
			_(
				"Set the ticket to “Waiting for Customer” when your work is complete, then request customer confirmation."
			),
			frappe.ValidationError,
		)

	h = cint(hours) or 24
	deadline = add_to_date(now_datetime(), hours=h)
	frappe.db.set_value(
		"Support Ticket",
		ticket_name,
		{
			"customer_resolution_deadline": deadline,
			"customer_confirmation_required": 1,
		},
	)

	doc = _get_portal_doc("Support Ticket", ticket_name)
	doc.append(
		"comments",
		{
			"comment_type": "System Update",
			"comment_by": user,
			"comment_on": frappe.utils.now(),
			"is_customer_visible": 1,
			"content": sanitize_html(
				_(
					"<p><strong>Confirmation requested</strong> — please confirm resolution in the portal within "
					"{0} hour(s). After the deadline, the ticket will be marked Resolved automatically if you do not.</p>"
				).format(h)
			),
		},
	)
	doc.save(ignore_permissions=True)
	return {"ok": True, "customer_resolution_deadline": str(deadline)}


@frappe.whitelist()
def get_portal_task_status_options():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	internal = user_sees_all_support_records(user)
	if internal:
		return {"options": list(_SUPPORT_TASK_STATUSES)}
	return {"options": sorted(_CUSTOMER_VISIBLE_TASK_STATUSES)}
