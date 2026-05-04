# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PrintechsSupportGoogleSettings(Document):
	pass


def get_settings() -> "PrintechsSupportGoogleSettings":
	"""Return the singleton Google integration settings document."""
	if getattr(frappe.local, "printechs_support_google_settings", None) is None:
		frappe.local.printechs_support_google_settings = frappe.get_single(
			"Printechs Support Google Settings"
		)
	return frappe.local.printechs_support_google_settings
