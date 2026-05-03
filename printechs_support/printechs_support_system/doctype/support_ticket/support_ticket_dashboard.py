from frappe import _


def get_data():
	return {
		"fieldname": "support_ticket",
		"transactions": [{"label": _("Tasks"), "items": ["Support Task"]}],
	}
