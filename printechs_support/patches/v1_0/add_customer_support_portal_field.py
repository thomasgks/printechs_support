from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "support_portal_enabled",
					"fieldtype": "Check",
					"label": "Support Portal Enabled",
					"insert_after": "customer_group",
					"default": "0",
				},
			],
		}
	)
