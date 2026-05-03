from frappe import _


def get_data():
	return {
		"fieldname": "support_agreement",
		"transactions": [{"label": _("Tickets"), "items": ["Support Ticket"]}],
	}
