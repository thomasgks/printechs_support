# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import nowdate, sanitize_html


class PRAIFAQ(Document):
	def before_insert(self):
		if not (self.faq_code or "").strip():
			year = nowdate()[:4]
			self.faq_code = make_autoname(f"PRAI-FAQ-{year}-.####")

	def validate(self):
		self.answer = sanitize_html(self.answer or "")
