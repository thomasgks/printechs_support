# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class PrintechsSupportSettings(Document):
	pass


def get_settings() -> "PrintechsSupportSettings":
	"""Return the singleton settings document (cached per request)."""
	if getattr(frappe.local, "printechs_support_settings", None) is None:
		frappe.local.printechs_support_settings = frappe.get_single("Printechs Support Settings")
	return frappe.local.printechs_support_settings


def is_prai_mvp_enabled() -> bool:
	"""Whether the Support Portal should expose the PRAI assistant entry."""
	try:
		if "prai_agent" in frappe.get_installed_apps():
			from prai_agent.prai_agent.doctype.prai_agent_settings.prai_agent_settings import (
				is_prai_mvp_enabled as _fn,
			)

			return _fn()
		return bool(frappe.db.get_single_value("Printechs Support Settings", "enable_prai_mvp"))
	except Exception:
		return False


def get_prai_openai_config() -> dict[str, str | bool | None]:
	"""OpenAI settings for PRAI (server-side only; never sent to portal clients)."""
	if "prai_agent" in frappe.get_installed_apps():
		from prai_agent.prai_agent.doctype.prai_agent_settings.prai_agent_settings import (
			get_prai_openai_config as _fn,
		)

		return _fn()
	settings = get_settings()
	api_key = None
	if settings.get("openai_api_key"):
		try:
			api_key = settings.get_password("openai_api_key")
		except Exception:
			api_key = None
	return {
		"enabled": bool(settings.get("enable_openai")),
		"chat_enabled": bool(settings.get("enable_openai_chat")),
		"model": (settings.get("openai_model") or "gpt-4o-mini").strip(),
		"api_key": api_key,
	}


def is_prai_openai_enabled() -> bool:
	"""Whether AI chat answers are configured (OpenAI + chat flag + API key)."""
	if "prai_agent" in frappe.get_installed_apps():
		from prai_agent.prai_agent.doctype.prai_agent_settings.prai_agent_settings import (
			is_prai_openai_enabled as _fn,
		)

		return _fn()
	from printechs_support.printechs_support_system.api.prai_openai import is_openai_chat_configured

	return is_openai_chat_configured()
