import frappe


def execute():
	if frappe.db.exists("DocType", "Support Agreement SLA"):
		frappe.delete_doc("DocType", "Support Agreement SLA", force=True)
		frappe.db.commit()
