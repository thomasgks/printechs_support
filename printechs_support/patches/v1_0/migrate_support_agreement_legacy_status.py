import frappe


def execute():
	"""Map removed status values to Expired after option list change."""
	frappe.db.sql(
		"""
		UPDATE `tabSupport Agreement`
		SET status = 'Expired'
		WHERE status IN ('Suspended', 'Closed')
		"""
	)
