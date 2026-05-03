# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

import frappe
from frappe import _

# Shown on /login as "Login to {app_name}" when users arrive from support portal links (avoids "Login to ERPNext").
_SUPPORT_LOGIN_APP_NAME = _("Printechs Support")


def update_website_context(context):
	"""Website-wide context tweaks (portal HTML shell is standalone; no web.html chrome)."""
	path = (context.pathname or context.path or "").strip("/")

	# Website login template uses: _("Login to {0}").format(app_name) — often "ERPNext" from system settings.
	# When redirect-to points at our portal (or classic support pages), use a customer-facing name instead.
	if path == "login":
		req = getattr(frappe.local, "request", None)
		if req and getattr(req, "args", None):
			rt = (req.args.get("redirect-to") or "").lower()
			if any(
				x in rt
				for x in (
					"support-portal",
					"support-tickets",
					"support-tasks",
				)
			):
				context["app_name"] = _SUPPORT_LOGIN_APP_NAME
