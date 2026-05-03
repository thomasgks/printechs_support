# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


from frappe.model.document import Document


class DelayReason(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING, Literal

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		is_active: DF.Check
		reason_name: DF.Data
		reason_type: Literal[
			"Printechs Delay", "Customer Delay", "Third Party Delay", "Shared Delay"
		]
	# end: auto-generated types

	pass
