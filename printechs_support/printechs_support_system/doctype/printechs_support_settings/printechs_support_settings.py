# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PrintechsSupportSettings(Document):
	pass


def get_settings() -> "PrintechsSupportSettings":
	"""Return the singleton settings document (cached per request)."""
	if getattr(frappe.local, "printechs_support_settings", None) is None:
		frappe.local.printechs_support_settings = frappe.get_single("Printechs Support Settings")
	return frappe.local.printechs_support_settings
