# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


from frappe.model.document import Document
from frappe.utils import now_datetime


class SupportTaskComment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attachment: DF.Attach | None
		comment_by: DF.Link | None
		comment_on: DF.Datetime
		comment_type: DF.Data
		content: DF.TextEditor
		is_customer_visible: DF.Check
		parent: DF.Data | None
		parentfield: DF.Data | None
		parenttype: DF.Data | None
	# end: auto-generated types

	def before_insert(self):
		if not self.comment_on:
			self.comment_on = now_datetime()
