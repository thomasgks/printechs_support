# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt


from frappe.model.document import Document


class SupportAgreementCoverageDetail(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_covered: DF.Check
		parent: DF.Data | None
		parentfield: DF.Data | None
		parenttype: DF.Data | None
		remarks: DF.SmallText | None
		resolution_sla_hours: DF.Float
		response_sla_hours: DF.Float
		service_category: DF.Data
	# end: auto-generated types

	pass
