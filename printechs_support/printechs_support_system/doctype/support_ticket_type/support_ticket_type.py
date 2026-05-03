# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


from frappe.model.document import Document


class SupportTicketType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING, Literal

	if TYPE_CHECKING:
		from frappe.types import DF

		default_priority: Literal["Low", "Medium", "High", "Critical"]
		default_sla_template: DF.Link | None
		default_team: DF.Link | None
		division: Literal["Software", "Industrial", "Retail"]
		is_active: DF.Check
		is_billable_by_default: DF.Check
		requires_approval: DF.Check
		ticket_type_name: DF.Data
	# end: auto-generated types

	pass
