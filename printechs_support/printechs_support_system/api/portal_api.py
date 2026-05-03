# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Whitelisted methods for the React customer portal (bootstrap + lists)."""

from collections import Counter
from html import escape as html_escape

import frappe
from frappe import _
from frappe.auth import LoginManager
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
from frappe.utils.file_manager import save_file
from werkzeug.utils import secure_filename

from printechs_support.permissions import (
	get_allowed_customers,
	user_can_access_support_portal,
	user_can_edit_portal_task_schedule,
	user_can_edit_portal_ticket_schedule,
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


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def portal_web_logout():
	"""Used by portal ``logoutUrl()``: end session and redirect browser to the support portal shell."""
	frappe.local.login_manager.logout()
	frappe.db.commit()
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/support-portal"


@frappe.whitelist(allow_guest=True)
def get_portal_bootstrap():
	"""Called on SPA load; guests must be allowed so we can show sign-in (not a misleading 'not whitelisted' error)."""
	user = frappe.session.user
	if user == "Guest":
		return {"logged_in": False}

	full_name = frappe.db.get_value("User", user, "full_name") or user
	customers = get_allowed_customers(user)
	internal = user_sees_all_support_records(user)

	return {
		"logged_in": True,
		"user": user,
		"full_name": full_name,
		"customers": customers,
		"internal": internal,
	}


_VALID_CREATE_PRIORITIES = frozenset({"Low", "Medium", "High", "Critical"})


@frappe.whitelist()
def get_portal_ticket_types():
	"""Active Support Ticket Types for the create-ticket form (customer and internal users)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	rows = frappe.get_all(
		"Support Ticket Type",
		filters={"is_active": 1},
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
		]
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
	"""Customers the current user may create Support Tickets for (portal)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if user_sees_all_support_records(user):
		rows = frappe.get_all(
			"Customer",
			fields=["name", "customer_name"],
			order_by="customer_name asc",
			limit_page_length=500,
		)
		return {
			"customers": [{"name": r.name, "customer_name": (r.customer_name or r.name).strip()} for r in rows],
		}

	names = get_allowed_customers(user)
	out = []
	for name in names:
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
):
	"""Create a Support Ticket from the portal (customer or internal user)."""
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

	desc = ""
	if description and str(description).strip():
		desc = sanitize_html(str(description).strip())
		if not strip_html(desc).strip():
			desc = ""
	if not desc:
		desc = f"<p>{html_escape(subject)}</p>"

	initial_status = get_initial_support_ticket_status()
	doc = frappe.get_doc(
		{
			"doctype": "Support Ticket",
			"naming_series": "SUP-TKT-.YYYY.-.#####",
			"subject": subject,
			"customer": cust,
			"ticket_type": tt,
			"priority": priority,
			"status": initial_status,
			"description": desc,
		}
	)
	doc.flags.priority_from_portal = 1
	doc.insert(ignore_permissions=True)

	return {
		"name": doc.name,
		"subject": doc.subject,
		"status": doc.status,
		"customer": doc.customer,
	}


@frappe.whitelist()
def get_portal_tickets(limit: int = 50):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	limit = min(int(limit), 100)

	if user_sees_all_support_records(user):
		return frappe.get_all(
			"Support Ticket",
			fields=["name", "subject", "status", "priority", "modified", "customer"],
			order_by="modified desc",
			limit_page_length=limit,
		)

	customers = get_allowed_customers(user)
	if not customers:
		return []

	return frappe.get_all(
		"Support Ticket",
		filters={"customer": ["in", customers]},
		fields=["name", "subject", "status", "priority", "modified", "customer"],
		order_by="modified desc",
		limit_page_length=limit,
	)


@frappe.whitelist()
def get_portal_tasks(limit: int = 50):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	limit = min(int(limit), 100)

	_task_fields = [
		"name",
		"subject",
		"status",
		"task_type",
		"modified",
		"support_ticket",
		"customer",
		"assigned_to_user",
		"due_date",
		"delay_owner",
		"delay_reason",
		"is_delayed",
		"delay_days",
		"creation",
	]

	if user_sees_all_support_records(user):
		tasks = frappe.get_all(
			"Support Task",
			fields=_task_fields,
			order_by="modified desc",
			limit_page_length=limit,
		)
	else:
		customers = get_allowed_customers(user)
		if not customers:
			return []

		tickets = frappe.get_all(
			"Support Ticket",
			filters={"customer": ["in", customers]},
			pluck="name",
		)
		if not tickets:
			return []

		tasks = frappe.get_all(
			"Support Task",
			filters={"support_ticket": ["in", tickets]},
			fields=_task_fields,
			order_by="modified desc",
			limit_page_length=limit,
		)

	names = [t["name"] for t in tasks]
	amap = _assignee_users_by_parent("Support Task Assignee", names)
	for t in tasks:
		t["assigned_users"] = amap.get(t["name"], [])
	return tasks


_TERMINAL_TICKET_STATUS = ("Closed", "Cancelled", "Resolved")
_TERMINAL_TASK_STATUS = ("Completed", "Cancelled")


def _task_scope_filters(user: str) -> dict:
	"""Filters for Support Task queries; ``{'empty': True}`` means no visible tasks."""
	if user_sees_all_support_records(user):
		return {}
	customers = get_allowed_customers(user)
	if not customers:
		return {"empty": True}
	tickets = frappe.get_all(
		"Support Ticket",
		filters={"customer": ["in", customers]},
		pluck="name",
	)
	if not tickets:
		return {"empty": True}
	return {"support_ticket": ["in", tickets]}


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
			"pending_tasks": 0,
			"overdue_tasks": 0,
			"completed_today": 0,
			"waiting_customer": 0,
			"waiting_internal": 0,
			"sla_breached": 0,
			"delayed_flagged": 0,
			"tasks_by_status": {},
			"assignee_load": [],
			"monthly_completion": [],
		}

	if user_sees_all_support_records(user):
		pending_tickets = frappe.db.count(
			"Support Ticket",
			{"status": ["not in", _TERMINAL_TICKET_STATUS]},
		)
	else:
		customers = get_allowed_customers(user)
		pending_tickets = frappe.db.count(
			"Support Ticket",
			{
				"customer": ["in", customers],
				"status": ["not in", _TERMINAL_TICKET_STATUS],
			},
		)

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
		"pending_tasks": int(pending_tasks),
		"overdue_tasks": int(overdue_tasks),
		"completed_today": int(completed_today),
		"waiting_customer": int(waiting_customer),
		"waiting_internal": int(waiting_internal),
		"sla_breached": int(sla_breached),
		"delayed_flagged": int(delayed_flagged),
		"tasks_by_status": tasks_by_status,
		"assignee_load": assignee_load,
		"monthly_completion": monthly_completion,
	}


def _assert_portal_ticket_access(user: str, ticket_name: str) -> None:
	if user_sees_all_support_records(user):
		return
	customers = get_allowed_customers(user)
	if not customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	cust = frappe.db.get_value("Support Ticket", ticket_name, "customer")
	if not cust or cust not in customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _assert_portal_task_access(user: str, task_name: str) -> None:
	if user_sees_all_support_records(user):
		return
	customers = get_allowed_customers(user)
	if not customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	ticket = frappe.db.get_value("Support Task", task_name, "support_ticket")
	if not ticket:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	cust = frappe.db.get_value("Support Ticket", ticket, "customer")
	if not cust or cust not in customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def get_portal_ticket(name: str):
	"""Single ticket for the React portal (no desk / web form redirect)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	name = (name or "").strip()
	if not name or not frappe.db.exists("Support Ticket", name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, name)
	# Read from DB so schedule fields are not stripped by Doc field-permission rules for portal users.
	row = frappe.db.get_value(
		"Support Ticket",
		name,
		[
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
			"modified",
			"opening_date",
			"due_date",
			"description",
			"customer_resolution_deadline",
			"customer_confirmation_required",
		],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	desc = row.get("description") or ""
	desc = strip_html(desc).strip() if desc else ""

	def _dt(val):
		return str(val) if val else None

	ticket_assignees = _assignee_users_by_parent("Support Ticket Assignee", [name]).get(name, [])
	tt_label = ""
	if row.ticket_type:
		tt_label = frappe.db.get_value("Support Ticket Type", row.ticket_type, "ticket_type_name") or row.ticket_type

	can_edit_ticket_schedule = user_can_edit_portal_ticket_schedule(user, name)

	return {
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
		"assigned_users": ticket_assignees,
		"modified": _dt(row.modified),
		"opening_date": _dt(row.opening_date),
		"due_date": _dt(row.due_date),
		"description": desc,
		"customer_resolution_deadline": _dt(row.customer_resolution_deadline),
		"customer_confirmation_required": int(row.customer_confirmation_required or 0),
		"can_edit_ticket_schedule": bool(can_edit_ticket_schedule),
	}


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

	task_assignees = _assignee_users_by_parent("Support Task Assignee", [name]).get(name, [])

	can_edit_task_schedule = user_can_edit_portal_task_schedule(user, name)

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
		"due_date": _dt(row.due_date),
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
		"can_edit_task_schedule": bool(can_edit_task_schedule),
	}


_SUPPORT_TICKET_STATUSES = (
	"Draft",
	"Open",
	"Acknowledged",
	"In Progress",
	"Waiting for Customer",
	"Waiting for Internal Team",
	"Waiting for Approval",
	"Resolved",
	"Closed",
	"Cancelled",
	"Reopened",
)
_TERMINAL_TICKET_STATUSES = frozenset({"Resolved", "Closed", "Cancelled"})
# Only after internal work is done: ticket should be waiting on the customer (not Open / In Progress / etc.).
_STATUSES_ELIGIBLE_FOR_CUSTOMER_CONFIRMATION_REQUEST = frozenset({"Waiting for Customer"})

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


def _serialize_comment_row(row: dict) -> dict:
	by = row.get("comment_by") or ""
	full = frappe.db.get_value("User", by, "full_name") if by else ""
	att = row.get("attachment")
	att_url = None
	if att:
		att_url = frappe.db.get_value("File", att, "file_url")
		if att_url and not str(att_url).startswith("http"):
			att_url = get_url(att_url)
	content = row.get("content") or ""
	content = sanitize_html(content) if content else ""
	reply_to = (row.get("in_reply_to") or "").strip() or None
	return {
		"name": row.get("name"),
		"comment_type": row.get("comment_type"),
		"comment_by": by,
		"author_name": full or by,
		"comment_on": str(row.get("comment_on")) if row.get("comment_on") else None,
		"is_customer_visible": int(row.get("is_customer_visible") or 0),
		"content": content,
		"in_reply_to": reply_to,
		"attachment": att,
		"attachment_url": att_url,
		"internal_only": not int(row.get("is_customer_visible") or 0),
	}


@frappe.whitelist()
def get_portal_ticket_comments(ticket_name: str):
	"""Comments on the ticket (child table). Customer portal users only see customer-visible rows."""
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

	return [_serialize_comment_row(r) for r in rows]


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
def add_portal_ticket_comment(ticket_name: str, content: str, is_internal_note=None, in_reply_to=None, attachment=None):
	"""Append a Support Ticket Comment row. Internal notes only for internal portal users.

	``in_reply_to``: optional name of another comment row on the same ticket (threaded reply).
	``attachment``: optional File name (from :func:`portal_upload_ticket_file`) linked to this ticket.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	ticket_name = (ticket_name or "").strip()
	if not ticket_name or not frappe.db.exists("Support Ticket", ticket_name):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	_assert_portal_ticket_access(user, ticket_name)

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

	doc = _get_portal_doc("Support Ticket", ticket_name)
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

	frappe.db.set_value(
		"Support Ticket",
		ticket_name,
		"last_customer_update_on" if visible else "last_internal_update_on",
		frappe.utils.now(),
	)

	return {"ok": True}


@frappe.whitelist()
def update_portal_ticket_status(ticket_name: str, status: str):
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
	if not internal:
		if status != "Resolved":
			frappe.throw(
				_("Customers can only confirm resolution by setting status to Resolved."),
				frappe.PermissionError,
			)
		deadline = frappe.db.get_value("Support Ticket", ticket_name, "customer_resolution_deadline")
		if not deadline:
			frappe.throw(
				_("Your support team has not opened a confirmation window for this ticket yet."),
				frappe.PermissionError,
			)
		if now_datetime() > get_datetime(deadline):
			frappe.throw(_("The confirmation period has ended."), frappe.ValidationError)
		cur = frappe.db.get_value("Support Ticket", ticket_name, "status")
		if cur in _TERMINAL_TICKET_STATUSES:
			frappe.throw(_("This ticket is already closed."), frappe.ValidationError)

	doc = _get_portal_doc("Support Ticket", ticket_name)
	old = doc.status
	if old == status:
		return {"ok": True, "status": status}

	# Workflow validates transitions by user role (see get_transitions). Portal users often lack
	# the workflow "allowed" role even when the API permits the target status. Set status via DB
	# (no workflow), then save only the new comment row so validate_workflow sees no transition.
	update_fields = {"status": status}
	if status in _TERMINAL_TICKET_STATUSES:
		update_fields["customer_resolution_deadline"] = None
		update_fields["customer_confirmation_required"] = 0

	frappe.db.set_value("Support Ticket", ticket_name, update_fields)
	doc = frappe.get_doc("Support Ticket", ticket_name)
	doc.append(
		"comments",
		{
			"comment_type": "System Update",
			"comment_by": user,
			"comment_on": frappe.utils.now(),
			"is_customer_visible": 1,
			"content": sanitize_html(
				f"<p><strong>Status</strong> updated from <em>{html_escape(old)}</em> to <em>{html_escape(status)}</em></p>"
			),
		},
	)
	doc.save(ignore_permissions=True)
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
		return {"ok": True, "due_date": str(out) if out else None}
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
		return {"ok": True, "due_date": str(out) if out else None}
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
		}

	doc.save(ignore_permissions=True)
	users = _assignee_users_by_parent("Support Ticket Assignee", [ticket_name]).get(ticket_name, [])
	return {"ok": True, "team": doc.team or "", "assigned_to": doc.assigned_to or "", "assigned_users": users}


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

	Customers only see ``Resolved`` when a technician has started a confirmation window
	(``customer_resolution_deadline``) that is still active. Pass ``ticket_name`` from the ticket detail page.
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
