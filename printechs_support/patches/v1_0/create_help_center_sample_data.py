import frappe


def execute():
	_categories()
	_articles()


def _ensure_category(name: str, module_area: str, description: str = "", sort_order: int = 0):
	if frappe.db.exists("Help Category", name):
		return name
	frappe.get_doc(
		{
			"doctype": "Help Category",
			"category_name": name,
			"module_area": module_area,
			"description": description,
			"sort_order": sort_order,
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	return name


def _categories():
	_ensure_category("WMS Help", "WMS", "Warehouse management guides and troubleshooting.", 10)
	_ensure_category("ASN Receiving", "WMS", "Receiving advance shipment notices in WMS.", 20)
	_ensure_category("Stock Transfer", "Stock", "Stock movement and transfer guides.", 30)
	_ensure_category("Support Ticket Help", "Support", "Customer support portal guides.", 40)
	_ensure_category("ERPNext Basics", "ERPNext", "General ERPNext user guidance.", 50)


def _ensure_article(title: str, category: str, **kwargs):
	if frappe.db.exists("Help Article", {"title": title, "category": category}):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Help Article",
			"title": title,
			"category": category,
			"module_area": kwargs.get("module_area") or "General",
			"related_doctype": kwargs.get("related_doctype"),
			"keywords": kwargs.get("keywords"),
			"summary": kwargs.get("summary"),
			"content": kwargs.get("content"),
			"allow_customer_view": kwargs.get("allow_customer_view", 0),
			"show_in_portal": 1,
			"show_in_desk": 1,
			"status": "Published",
			"sort_order": kwargs.get("sort_order", 0),
		}
	)
	doc.insert(ignore_permissions=True)


def _articles():
	_ensure_article(
		"How to Receive ASN in WMS",
		"ASN Receiving",
		module_area="WMS",
		related_doctype="WMS ASN" if frappe.db.exists("DocType", "WMS ASN") else None,
		keywords="ASN, receiving, carton, barcode",
		summary="Basic steps for receiving an ASN in WMS.",
		content="<p>Open the ASN receiving screen, scan or select the ASN, verify cartons, and complete receiving after validation.</p>",
		allow_customer_view=0,
		sort_order=10,
	)
	_ensure_article(
		"Barcode Not Scanning in Mobile App",
		"WMS Help",
		module_area="WMS",
		keywords="barcode, scanner, mobile, enter key",
		summary="Troubleshooting steps when scanner input is not accepted.",
		content="<p>Check scanner keyboard mode, confirm the cursor is inside the barcode field, and verify the scanner sends Enter after each scan.</p>",
		allow_customer_view=0,
		sort_order=20,
	)
	_ensure_article(
		"How to Create a Support Ticket",
		"Support Ticket Help",
		module_area="Support",
		related_doctype="Support Ticket",
		keywords="support ticket, portal, create ticket",
		summary="Create a new support ticket from the Printechs Support Portal.",
		content="<p>Sign in to the support portal, open Tickets, click New Ticket, enter the subject and details, then submit.</p>",
		allow_customer_view=1,
		sort_order=30,
	)
	_ensure_article(
		"How to Reply to Technician Request",
		"Support Ticket Help",
		module_area="Support",
		related_doctype="Support Ticket",
		keywords="reply, technician, customer request, support portal",
		summary="Reply to a technician when more information is requested.",
		content="<p>Open the ticket from the portal, read the technician request, add your reply in the communication panel, and submit.</p>",
		allow_customer_view=1,
		sort_order=40,
	)
