# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

from datetime import timedelta
from html import escape as html_escape

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime, validate_email_address

from printechs_support.permissions import (
	internal_user_may_access_support_ticket,
	user_has_unrestricted_support_ticket_catalog,
	user_sees_all_support_records,
)
from printechs_support.printechs_support_system.doctype.printechs_support_google_settings.printechs_support_google_settings import (
	get_settings,
)

GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
TIME_ZONE = "Asia/Riyadh"

_MEET_CREATOR_ROLES = frozenset(
	{
		"Administrator",
		"System Manager",
		"Support Team",
		"Printechs Support Coordinator",
		"Printechs Support Engineer",
		"Printechs Support Project Manager",
	}
)


def _google_dependency_error() -> str:
	return _(
		"Google Calendar libraries are not installed. Run: "
		"bench pip install google-api-python-client google-auth google-auth-oauthlib"
	)


def _assert_can_manage_meet(ticket_id: str) -> None:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	roles = set(frappe.get_roles(user))
	if not (_MEET_CREATOR_ROLES & roles):
		frappe.throw(_("You do not have permission to create Google Meet links."), frappe.PermissionError)

	if user_has_unrestricted_support_ticket_catalog(user):
		return
	if user_sees_all_support_records(user) and internal_user_may_access_support_ticket(user, ticket_id):
		return
	if "System Manager" in roles:
		return
	frappe.throw(_("You do not have access to this support ticket."), frappe.PermissionError)


def _settings():
	settings = get_settings()
	if not cint(settings.enabled):
		frappe.throw(_("Google Meet integration is not enabled."), frappe.ValidationError)
	return settings


def _setting_password(settings, fieldname: str) -> str:
	value = settings.get_password(fieldname) or ""
	return value.strip()


def _google_calendar_service(settings):
	try:
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
	except ImportError:
		frappe.throw(_google_dependency_error(), frappe.ValidationError)

	client_id = (settings.google_client_id or "").strip()
	client_secret = _setting_password(settings, "google_client_secret")
	refresh_token = _setting_password(settings, "google_refresh_token")

	if not client_id or not client_secret or not refresh_token:
		frappe.throw(
			_(
				"Google Meet credentials are incomplete. Set Google Client ID, Client Secret, "
				"and Refresh Token in Printechs Support Google Settings."
			),
			frappe.ValidationError,
		)

	credentials = Credentials(
		token=None,
		refresh_token=refresh_token,
		token_uri=GOOGLE_TOKEN_URI,
		client_id=client_id,
		client_secret=client_secret,
		scopes=[GOOGLE_CALENDAR_SCOPE],
	)
	return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _ticket_or_404(ticket_id: str):
	ticket_id = (ticket_id or "").strip()
	if not ticket_id or not frappe.db.exists("Support Ticket", ticket_id):
		frappe.throw(_("Support Ticket not found."), frappe.DoesNotExistError)
	return frappe.get_doc("Support Ticket", ticket_id)


def _customer_email(ticket) -> str | None:
	email = (ticket.contact_email or "").strip()
	if not email:
		return None
	try:
		validate_email_address(email, True)
		return email
	except Exception:
		return None


def _meeting_title(settings, ticket_id: str) -> str:
	template = (settings.meeting_title_template or "Support Meeting - {ticket_id}").strip()
	try:
		return template.format(ticket_id=ticket_id)
	except Exception:
		return f"Support Meeting - {ticket_id}"


def _meeting_window(start_time, duration_minutes: int):
	start = get_datetime(start_time) if start_time else now_datetime()
	duration = max(cint(duration_minutes) or 30, 1)
	end = start + timedelta(minutes=duration)
	return start, end


def _extract_meet_url(event: dict) -> str:
	link = (event or {}).get("hangoutLink")
	if link:
		return link
	for entry in ((event or {}).get("conferenceData") or {}).get("entryPoints") or []:
		if entry.get("entryPointType") == "video" and entry.get("uri"):
			return entry.get("uri")
	return ""


def _build_calendar_event(settings, ticket, start, end, customer_email: str | None) -> dict:
	event = {
		"summary": _meeting_title(settings, ticket.name),
		"description": f"Support ticket live meeting for {ticket.name}",
		"start": {"dateTime": start.isoformat(), "timeZone": TIME_ZONE},
		"end": {"dateTime": end.isoformat(), "timeZone": TIME_ZONE},
		"conferenceData": {
			"createRequest": {
				"requestId": frappe.generate_hash(length=16),
				"conferenceSolutionKey": {"type": "hangoutsMeet"},
			}
		},
	}
	if customer_email:
		event["attendees"] = [{"email": customer_email}]
	return event


def _append_ticket_comment(ticket, message: str, *, visible: bool = True) -> None:
	ticket.append(
		"comments",
		{
			"comment_type": "System Update",
			"comment_by": frappe.session.user,
			"comment_on": frappe.utils.now(),
			"is_customer_visible": 1 if visible else 0,
			"content": f"<p>{html_escape(message)}</p>",
		},
	)


def _save_ticket_without_comment_email(ticket) -> None:
	ticket.flags.skip_comment_notification_hook = True
	ticket.save(ignore_permissions=True)


def _meet_email_body(ticket, meeting_url: str) -> str:
	customer_name = ticket.customer_name or ticket.customer or _("Customer")
	return f"""<div style="font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#1e293b;line-height:1.55;max-width:560px;">
<p>{_("Dear")} {html_escape(customer_name)},</p>
<p>{_("A live support meeting has been created for your ticket")} <strong>{html_escape(ticket.name)}</strong>.</p>
<p>{_("Please click the link below to join:")}</p>
<p><a href="{html_escape(meeting_url)}" style="color:#1d4ed8;font-weight:700;">{html_escape(meeting_url)}</a></p>
<p>{_("This link will open in Google Meet.")}</p>
<p>{_("Regards,")}<br>{_("Support Team")}</p>
</div>"""


def _send_meet_email(ticket, meeting_url: str) -> tuple[bool, str | None]:
	email = _customer_email(ticket)
	if not email:
		return False, _("Customer email is missing or invalid. Meet link was created but email was not sent.")

	subject = _("Live Support Meeting Link for Ticket {0}").format(ticket.name)
	frappe.sendmail(
		recipients=[email],
		subject=subject,
		message=_meet_email_body(ticket, meeting_url),
		reference_doctype="Support Ticket",
		reference_name=ticket.name,
		delayed=False,
	)
	return True, None


def _mark_customer_notified(ticket, message: str) -> None:
	ticket.last_meet_notification_on = now_datetime()
	ticket.live_support_status = "Customer Notified"
	_append_ticket_comment(ticket, message, visible=True)
	_save_ticket_without_comment_email(ticket)


@frappe.whitelist()
def create_google_meet(ticket_id, start_time=None, duration_minutes=30, notify_customer=1):
	"""Create or return a unique Google Meet link for a Support Ticket."""
	ticket = _ticket_or_404(ticket_id)
	_assert_can_manage_meet(ticket.name)

	existing_url = (ticket.google_meet_url or "").strip()
	if existing_url:
		return {
			"success": True,
			"meeting_url": existing_url,
			"event_id": ticket.google_meet_event_id,
			"message": _("Google Meet link already exists"),
		}

	settings = _settings()
	duration = cint(duration_minutes) or cint(settings.default_meeting_duration) or 30
	start, end = _meeting_window(start_time, duration)
	customer_email = _customer_email(ticket)
	event_body = _build_calendar_event(settings, ticket, start, end, customer_email)
	calendar_id = (settings.calendar_id or "primary").strip() or "primary"

	try:
		event = (
			_google_calendar_service(settings)
			.events()
			.insert(
				calendarId=calendar_id,
				body=event_body,
				conferenceDataVersion=1,
				sendUpdates="none",
			)
			.execute()
		)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Google Meet creation failed")
		frappe.throw(_("Could not create Google Meet link: {0}").format(str(exc)), frappe.ValidationError)

	meeting_url = _extract_meet_url(event)
	if not meeting_url:
		frappe.throw(_("Google Calendar did not return a Google Meet link."), frappe.ValidationError)

	ticket.google_meet_url = meeting_url
	ticket.google_meet_event_id = event.get("id") or ""
	ticket.google_meet_created_on = now_datetime()
	ticket.google_meet_created_by = frappe.session.user
	ticket.live_support_status = "Meet Link Generated"
	_append_ticket_comment(ticket, _("Google Meet link generated by {0}").format(frappe.session.user))
	_save_ticket_without_comment_email(ticket)

	warning = None
	should_notify = cint(notify_customer) and cint(settings.auto_email_customer)
	if should_notify:
		try:
			sent, warning = _send_meet_email(ticket, meeting_url)
			if sent:
				_mark_customer_notified(ticket, _("Customer notified with Google Meet link"))
		except Exception as exc:
			frappe.log_error(frappe.get_traceback(), "Google Meet customer email failed")
			warning = _("Meet link was created, but customer email failed: {0}").format(str(exc))
	elif not customer_email:
		warning = _("Customer email is missing or invalid. Meet link was created but email was not sent.")

	return {
		"success": True,
		"meeting_url": meeting_url,
		"event_id": ticket.google_meet_event_id,
		"message": _("Google Meet link created"),
		"warning": warning,
	}


@frappe.whitelist()
def resend_google_meet_link(ticket_id):
	"""Resend the existing Google Meet link to the ticket customer."""
	ticket = _ticket_or_404(ticket_id)
	_assert_can_manage_meet(ticket.name)
	meeting_url = (ticket.google_meet_url or "").strip()
	if not meeting_url:
		frappe.throw(_("Create a Google Meet link before resending."), frappe.ValidationError)

	sent, warning = _send_meet_email(ticket, meeting_url)
	if sent:
		_mark_customer_notified(ticket, _("Customer notified with Google Meet link"))

	return {
		"success": sent,
		"meeting_url": meeting_url,
		"event_id": ticket.google_meet_event_id,
		"message": _("Google Meet link resent") if sent else _("Google Meet link was not sent"),
		"warning": warning,
	}
