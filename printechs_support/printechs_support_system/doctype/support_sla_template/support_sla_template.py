# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


from frappe.model.document import Document


class SupportSLATemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING, Literal

	if TYPE_CHECKING:
		from frappe.types import DF

		division: Literal["Software", "Industrial", "Retail"]
		first_response_hours: DF.Float
		priority: Literal["Low", "Medium", "High", "Critical"]
		resolution_hours: DF.Float
		template_name: DF.Data
		ticket_type: DF.Link
		working_hours_only: DF.Check
	# end: auto-generated types

	pass
