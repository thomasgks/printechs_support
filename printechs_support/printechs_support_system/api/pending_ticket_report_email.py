from __future__ import annotations

import re
from html import escape as html_escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, date_diff, format_datetime, get_url, getdate, now_datetime, today
from frappe.utils.xlsxutils import make_xlsx


PENDING_TICKET_STATUSES = (
	"Open",
	"Assigned",
	"In Progress",
	"Waiting for Customer",
	"Waiting for Technician",
)

REPORT_COLUMNS = (
	("ticket", _("Ticket")),
	("subject", _("Subject")),
	("customer_name", _("Customer Name")),
	("status", _("Status")),
	("priority", _("Priority")),
	("ticket_type", _("Ticket Type")),
	("opening_date", _("Opening Date")),
	("due_date", _("Due Date")),
	("first_response_on", _("First Response Date")),
	("resolution_due", _("Resolution Date")),
	("resolved_on", _("Resolved On")),
	("closed_on", _("Closed On")),
	("delay_reason", _("Delay Reason")),
	("delay_remarks", _("Delay Remarks")),
)


def send_pending_ticket_sla_report_if_due(*, force: bool = False) -> None:
	"""Send the pending-ticket SLA report using the configured day interval."""
	settings = frappe.get_single("Printechs Support Settings")
	last_sent = settings.get("last_pending_ticket_report_sent_on")
	interval_days = max(cint(settings.get("pending_ticket_report_interval_days")) or 2, 1)
	if not force and last_sent and date_diff(getdate(today()), getdate(last_sent)) < interval_days:
		return

	sent_count = 0
	for team in _get_active_support_teams():
		recipients = _get_team_recipients(team, settings)
		if not recipients:
			continue
		rows = get_pending_ticket_report_rows(team=team.name)
		if not rows:
			continue
		_send_report(recipients, rows, settings=settings, team_label=team.team_name or team.name)
		sent_count += 1

	fallback_recipients = _split_emails(settings.get("pending_ticket_report_recipients"))
	if fallback_recipients:
		unassigned_rows = get_pending_ticket_report_rows(unassigned=True)
		if unassigned_rows:
			_send_report(
				fallback_recipients,
				unassigned_rows,
				settings=settings,
				team_label=_("Unassigned Tickets"),
			)
			sent_count += 1

	if sent_count:
		settings.db_set("last_pending_ticket_report_sent_on", now_datetime(), update_modified=False)


@frappe.whitelist()
def send_pending_ticket_sla_report_now() -> dict:
	"""Manual trigger for administrators to test the pending-ticket report email."""
	if not frappe.has_permission("Printechs Support Settings", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	send_pending_ticket_sla_report_if_due(force=True)
	return {"ok": True}


def get_pending_ticket_report_rows(team: str | None = None, unassigned: bool = False) -> list[dict]:
	conditions = [
		"st.docstatus < 2",
		"st.status IN %(statuses)s",
	]
	params: dict = {"statuses": PENDING_TICKET_STATUSES}
	if team:
		conditions.append("st.team = %(team)s")
		params["team"] = team
	elif unassigned:
		conditions.append("IFNULL(st.team, '') = ''")

	return frappe.db.sql(
		f"""
		SELECT
			st.name AS ticket,
			st.subject AS subject,
			COALESCE(NULLIF(st.customer_name, ''), st.customer) AS customer_name,
			st.status AS status,
			st.priority AS priority,
			st.ticket_type AS ticket_type,
			st.opening_date AS opening_date,
			st.due_date AS due_date,
			st.first_response_on AS first_response_on,
			st.resolution_due AS resolution_due,
			st.resolved_on AS resolved_on,
			st.closed_on AS closed_on,
			IFNULL(dr.reason_name, st.delay_reason) AS delay_reason,
			st.delay_remarks AS delay_remarks
		FROM `tabSupport Ticket` st
		LEFT JOIN `tabDelay Reason` dr ON dr.name = st.delay_reason
		WHERE {" AND ".join(conditions)}
		ORDER BY
			st.due_date IS NULL ASC,
			st.due_date ASC,
			FIELD(st.priority, 'Critical', 'High', 'Medium', 'Low') ASC,
			st.opening_date DESC
		""",
		params,
		as_dict=True,
	)


def build_pending_ticket_report_html(rows: list[dict], *, settings=None, team_label: str | None = None) -> str:
	count = len(rows)
	generated_on = format_datetime(now_datetime())
	period_note = _("Pending tickets only. Hold, Resolved, Closed, and Cancelled tickets are excluded.")
	custom_message = ""
	if settings:
		custom_message = _format_setting_template(settings.get("pending_ticket_report_message"), rows, team_label)
	custom_message_html = _plain_text_to_html(custom_message) if custom_message else _plain_text_to_html(
		_(
			"Dear Support Team,\n\nPlease find below the pending ticket SLA and delay report. "
			"The Excel attachment contains the same list for filtering and follow-up."
		)
	)

	if not rows:
		body = f"""
<p style="margin:16px 0 0;color:#475569;">{html_escape(_("There are no pending support tickets."))}</p>
"""
	else:
		body = _build_table_html(rows)

	return f"""<div style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;font-size:13px;line-height:1.45;">
<div style="max-width:1180px;">
<h2 style="margin:0 0 6px;font-size:20px;color:#0f172a;">{html_escape(_("Pending Ticket SLA and Delay Report"))}</h2>
<p style="margin:0 0 12px;color:#475569;">
{html_escape(_("Generated on"))}: {html_escape(generated_on)}<br>
{html_escape(_("Support Team"))}: <strong>{html_escape(team_label or _("All Teams"))}</strong><br>
{html_escape(_("Pending tickets"))}: <strong>{count}</strong><br>
{html_escape(period_note)}
</p>
<div style="margin:0 0 14px;color:#334155;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;">
{custom_message_html}
</div>
{body}
<p style="margin:14px 0 0;color:#64748b;font-size:12px;">
{html_escape(_("The attached Excel file contains the same ticket list for filtering and follow-up."))}
</p>
</div>
</div>"""


def build_pending_ticket_report_xlsx(rows: list[dict]) -> dict:
	data = [[label for _, label in REPORT_COLUMNS]]
	for row in rows:
		data.append([_excel_value(row.get(field)) for field, _label in REPORT_COLUMNS])
	xlsx = make_xlsx(data, "Pending Tickets", column_widths=[18, 42, 28, 18, 12, 22, 20, 20, 20, 20, 20, 20, 24, 44])
	return {
		"fname": f"pending-ticket-sla-report-{today()}.xlsx",
		"fcontent": xlsx.getvalue(),
	}


def _build_table_html(rows: list[dict]) -> str:
	headers = "".join(
		f'<th style="{_th_style()}">{html_escape(str(label))}</th>' for _field, label in REPORT_COLUMNS
	)
	body_rows = []
	for row in rows:
		cells = []
		for field, _label in REPORT_COLUMNS:
			value = _html_value(row.get(field))
			if field == "ticket" and value != "—":
				url = _portal_ticket_url(value)
				value = f'<a href="{html_escape(url)}" style="color:#2563eb;text-decoration:none;font-weight:600;">{html_escape(value)}</a>'
			else:
				value = html_escape(value)
			cells.append(f'<td style="{_td_style()}">{value}</td>')
		body_rows.append(f"<tr>{''.join(cells)}</tr>")

	return f"""<div style="overflow-x:auto;">
<table style="border-collapse:collapse;width:100%;min-width:1100px;border:1px solid #e2e8f0;">
<thead><tr>{headers}</tr></thead>
<tbody>{''.join(body_rows)}</tbody>
</table>
</div>"""


def _send_report(recipients: list[str], rows: list[dict], *, settings, team_label: str) -> None:
	message = build_pending_ticket_report_html(rows, settings=settings, team_label=team_label)
	attachment = build_pending_ticket_report_xlsx(rows)
	subject = _format_setting_template(
		settings.get("pending_ticket_report_subject") or _("Pending Ticket SLA Report - {team} - {date}"),
		rows,
		team_label,
	)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		attachments=[attachment],
		delayed=False,
	)


def _portal_ticket_url(ticket_name: str) -> str:
	base = get_url().rstrip("/")
	name = (ticket_name or "").strip()
	if not name:
		return f"{base}/support-portal"
	return f"{base}/support-portal/tickets/{quote(name)}"


def _get_active_support_teams() -> list[dict]:
	return frappe.get_all(
		"Support Team",
		filters={"is_active": 1},
		fields=["name", "team_name", "default_email", "team_lead_email"],
		order_by="team_name asc, name asc",
	)


def _get_team_recipients(team, settings) -> list[str]:
	recipients = _collect_support_team_emails(team.name)
	if recipients:
		return recipients
	return _split_emails(settings.get("pending_ticket_report_recipients"))


def _format_setting_template(template: str | None, rows: list[dict], team_label: str | None = None) -> str:
	template = (template or "").strip()
	if not template:
		return ""
	try:
		return template.format(date=today(), count=len(rows), team=team_label or _("All Teams"))
	except Exception:
		return template


def _plain_text_to_html(text: str) -> str:
	lines = html_escape(text or "").splitlines()
	if not lines:
		return ""
	return "<br>".join(lines)


def _split_emails(raw: str | None) -> list[str]:
	out: list[str] = []
	for item in re.split(r"[\s,;]+", raw or ""):
		email = _normalize_email(item)
		if email and email not in out:
			out.append(email)
	return out


def _collect_support_team_emails(team_name: str) -> list[str]:
	out: list[str] = []

	def add(email: str | None) -> None:
		email = _normalize_email(email)
		if email and email not in out:
			out.append(email)

	team = frappe.db.get_value(
		"Support Team",
		team_name,
		["default_email", "team_lead_email"],
		as_dict=True,
	)
	if team:
		add(team.default_email)
		add(team.team_lead_email)
	for user in frappe.get_all(
		"Support Team Member",
		filters={"parent": team_name, "parenttype": "Support Team"},
		pluck="user",
	):
		add(frappe.db.get_value("User", user, "email"))

	return out


def _normalize_email(email: str | None) -> str | None:
	email = (email or "").strip()
	if not email:
		return None
	try:
		from frappe.utils import validate_email_address

		validate_email_address(email, True)
		return email.lower()
	except Exception:
		return None


def _html_value(value) -> str:
	if value is None or value == "":
		return "—"
	if hasattr(value, "strftime"):
		return format_datetime(value)
	return str(value)


def _excel_value(value):
	if value is None:
		return ""
	return value


def _th_style() -> str:
	return "background:#f1f5f9;color:#334155;padding:8px;border:1px solid #e2e8f0;text-align:left;font-size:12px;"


def _td_style() -> str:
	return "padding:7px 8px;border:1px solid #e2e8f0;vertical-align:top;color:#0f172a;"
