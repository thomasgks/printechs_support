# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""Curated PRAI FAQ catalog for Modern POS, ERPNext, and Support Portal."""

from __future__ import annotations

import frappe

PRAI_FAQ_CATALOG: list[dict] = [
	{
		"title": "How to set up a cashier in ERPNext",
		"question": "How do I create or set up a cashier user in ERPNext for POS?",
		"keywords": "cashier, pos user, teller, employee, user, role, pos profile, login, erpnext",
		"category": "ERPNext",
		"module_area": "ERPNext",
		"sort_order": 10,
		"answer": (
			"<p><strong>To set up a cashier in ERPNext:</strong></p>"
			"<ol>"
			"<li>Create or open the <strong>Employee</strong> record for the cashier.</li>"
			"<li>Create a <strong>User</strong> linked to that employee and assign POS/cashier roles "
			"(for example <em>Accounts User</em> plus your Modern POS role).</li>"
			"<li>Open <strong>POS Profile</strong>, add the user under allowed users, and confirm "
			"<strong>Company</strong>, warehouse, price list, and payment modes.</li>"
			"<li>Sync Modern POS store profile so the cashier can sign in on the terminal.</li>"
			"</ol>"
		),
	},
	{
		"title": "How to set up a store manager in ERPNext",
		"question": "How do I configure a store manager user for POS and approvals?",
		"keywords": "store manager, manager, supervisor, employee, user, role, pos profile, approval, erpnext",
		"category": "ERPNext",
		"module_area": "ERPNext",
		"sort_order": 11,
		"answer": (
			"<p>Create the manager as an <strong>Employee</strong> and <strong>User</strong>, assign roles that "
			"allow POS access plus any manager approvals your site uses (discount override, returns, shift close).</p>"
			"<p>Add the user to the correct <strong>POS Profile</strong> and Modern POS store profile. "
			"Managers usually need access to reports, shift summary, and override permissions configured in ERPNext.</p>"
		),
	},
	{
		"title": "How to configure POS Profile in ERPNext",
		"question": "What should I set in POS Profile for Modern POS?",
		"keywords": "pos profile, configure, setup, warehouse, company, payment mode, price list, erpnext",
		"category": "ERPNext",
		"module_area": "ERPNext",
		"sort_order": 12,
		"answer": (
			"<p>In <strong>POS Profile</strong>, set Company, warehouse, price list, allowed payment modes, "
			"print settings, and users allowed on the terminal. Link the profile to the store or branch used in Modern POS.</p>"
			"<p>After saving, sync the store profile in Modern POS so terminals receive the latest configuration.</p>"
		),
	},
	{
		"title": "How to create an item with barcode in ERPNext",
		"question": "How do I add a product barcode for POS scanning?",
		"keywords": "item, barcode, product, sku, create item, scanning, erpnext, stock",
		"category": "Stock",
		"module_area": "ERPNext",
		"sort_order": 13,
		"answer": (
			"<p>Create or open the <strong>Item</strong>, add the barcode in the barcodes table (or item barcode field), "
			"ensure the item is stocked in the POS warehouse, and sync Modern POS.</p>"
			"<p>If the scan fails at checkout, confirm the barcode type matches the scanner output and that the item is not disabled.</p>"
		),
	},
	{
		"title": "How to check stock balance in ERPNext",
		"question": "Where can I see available stock quantity?",
		"keywords": "stock balance, inventory, quantity, warehouse, stock ledger, available qty, erpnext",
		"category": "Stock",
		"module_area": "ERPNext",
		"sort_order": 14,
		"answer": (
			"<p>Use <strong>Stock Balance</strong> report or open the item stock summary for the warehouse linked to your store.</p>"
			"<p>POS shows sellable quantity from the configured warehouse after sync. If POS stock differs from ERPNext, run sync and check pending POS invoices or draft entries.</p>"
		),
	},
	{
		"title": "How to transfer stock between warehouses",
		"question": "How do I move stock from main warehouse to store?",
		"keywords": "stock transfer, warehouse, material transfer, stock entry, inventory move, erpnext",
		"category": "Stock",
		"module_area": "ERPNext",
		"sort_order": 15,
		"answer": (
			"<p>Create a <strong>Stock Entry</strong> (Material Transfer) from source warehouse to the store/POS warehouse, submit it, then sync Modern POS.</p>"
			"<p>Verify quantities on the Stock Balance report before opening the store.</p>"
		),
	},
	{
		"title": "How to push a new item to Modern POS",
		"question": "What is the procedure to push a new item into Modern POS?",
		"keywords": "push item, new item, add item, upload item, sync item, modern pos, pos item, custom_is_pos, stock item, price list, item price, master data",
		"category": "Stock",
		"module_area": "Modern POS",
		"sort_order": 9,
		"answer": (
			"<p><strong>Procedure to push a new item to Modern POS</strong></p>"
			"<ol>"
			"<li><strong>Stock Item</strong> — Open the Item and enable <strong>Stock Item</strong> "
			"(Maintain Stock). Non-stock items are not sold through POS inventory flow.</li>"
			"<li><strong>POS flag</strong> — Enable <strong>Is POS</strong> (<code>custom_is_pos</code> on Item). "
			"Only items flagged for POS are sent to Modern POS terminals.</li>"
			"<li><strong>Barcode</strong> — Add barcode(s) on the Item if cashiers scan at checkout.</li>"
			"<li><strong>Price</strong> — Create an <strong>Item Price</strong> in the price list linked to your "
			"<strong>POS Profile</strong> (selling rate required).</li>"
			"<li><strong>Warehouse stock</strong> — Ensure quantity exists in the warehouse used by the store/POS Profile "
			"(Stock Entry or Purchase Receipt if needed).</li>"
			"<li><strong>Sync Modern POS</strong> — Run <strong>Sync</strong> on the terminal (or store profile sync) "
			"to download the new item, price, and stock.</li>"
			"<li><strong>Test</strong> — Search or scan the item on POS and post a test sale.</li>"
			"</ol>"
			"<p>If the item still does not appear, confirm the item is not disabled, variants inherit POS flag from the template, "
			"and the POS Profile price list matches the Item Price you created.</p>"
		),
	},
	{
		"title": "How to set up Modern POS step by step",
		"question": "How do I setup or install Modern POS? Please provide step by step procedure.",
		"keywords": "modern pos, setup, set up, install, configure, store profile, terminal, step by step, procedure, implementation, deployment",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 8,
		"answer": (
			"<p><strong>Step-by-step: set up Modern POS</strong></p>"
			"<ol>"
			"<li><strong>ERPNext master data</strong> — Confirm Company, warehouse, items/barcodes, price list, "
			"customers (if needed), payment modes, and POS Profile are configured.</li>"
			"<li><strong>Users &amp; roles</strong> — Create Employee/User for each cashier or manager and allow them on the POS Profile.</li>"
			"<li><strong>Store profile</strong> — In Modern POS / ERPNext store setup, link the store to Company, warehouse, "
			"POS Profile, and server URL for your ERPNext site.</li>"
			"<li><strong>Terminal install</strong> — Install Modern POS on the terminal (Windows/Android as applicable), "
			"set server URL, and sign in with the store profile user.</li>"
			"<li><strong>Initial sync</strong> — Run full <strong>Sync</strong> to download items, prices, promotions, and customers.</li>"
			"<li><strong>Test sale</strong> — Post a test sale, verify stock and POS Invoice in ERPNext, receipt print, and payment modes.</li>"
			"<li><strong>Go live</strong> — Open shift, train cashiers, and schedule regular sync (especially after master data changes).</li>"
			"</ol>"
			"<p>If any step fails, note the exact error message and create a support ticket with your store name and terminal type.</p>"
		),
	},
	{
		"title": "Modern POS is offline — can I still sell?",
		"question": "Can I continue billing when internet is down?",
		"keywords": "offline, internet, connectivity, network, sell, billing, modern pos",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 20,
		"answer": (
			"<p>Modern POS can continue basic sales offline when the store profile allows it. Sales queue locally and sync when internet returns.</p>"
			"<p>Live stock checks, new promotions, loyalty, and e-wallet updates may be limited until the terminal reconnects.</p>"
		),
	},
	{
		"title": "How to sync Modern POS with ERPNext",
		"question": "How do I refresh master data and post sales to ERPNext?",
		"keywords": "sync, synchronize, refresh, master data, upload sales, erpnext, modern pos, store profile",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 21,
		"answer": (
			"<p>Ensure the terminal has internet, sign in with a valid store profile, and run <strong>Sync</strong> from Modern POS.</p>"
			"<p>Sync downloads items, prices, promotions, and customers, and uploads completed sales to ERPNext. "
			"If sync fails, check server URL, credentials, and pending error logs on the support portal.</p>"
		),
	},
	{
		"title": "How to open and close POS shift",
		"question": "How does shift opening and closing work on Modern POS?",
		"keywords": "shift, opening, closing, cash float, end of day, pos shift, modern pos",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 22,
		"answer": (
			"<p>At start of day, open shift with opening cash float. Cashiers bill during the shift. "
			"At close, count cash, reconcile payment modes, and close shift in Modern POS.</p>"
			"<p>Closing posts summary data to ERPNext depending on your configuration. Managers should review variance before final close.</p>"
		),
	},
	{
		"title": "How to login to Modern POS",
		"question": "Cashier cannot login to Modern POS terminal",
		"keywords": "login, sign in, password, user, cashier, modern pos, authentication",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 23,
		"answer": (
			"<p>Confirm the user exists in ERPNext, is allowed on the POS Profile, and the store profile has synced.</p>"
			"<p>Check username/password, terminal date/time, and internet for first login. Reset password from ERPNext User if needed, then sync again.</p>"
		),
	},
	{
		"title": "How to view list of promotions in Modern POS",
		"question": "Can I have a list of promotions available in Modern POS?",
		"keywords": "list promotions, list of promotions, available promotions, view promotions, show promotions, see promotions, active promotions, promotion list, which promotions, what promotions, modern pos, erpnext, pos promotion",
		"category": "Promotions",
		"module_area": "Modern POS",
		"sort_order": 29,
		"answer": (
			"<p><strong>Where to see available promotions</strong></p>"
			"<ol>"
			"<li><strong>ERPNext master list</strong> — Open the <strong>POS Promotion</strong> list in ERPNext (Modern POS module). "
			"Filter by <strong>Active</strong>, then review promotion name/code, start/end dates, and store or warehouse scope.</li>"
			"<li><strong>Sync Modern POS</strong> — Run <strong>Sync</strong> on the terminal so active promotions for your store are downloaded.</li>"
			"<li><strong>At checkout</strong> — Eligible promotions usually apply automatically when items, customer, dates, and store rules match. "
			"Add qualifying items and confirm the discount on the line or bill total.</li>"
			"<li><strong>On the terminal</strong> — If your Modern POS version includes a Promotions or Offers screen, open it after sync to review cached active promotions for the store.</li>"
			"</ol>"
			"<p>PRAI shows guidance only — it cannot display your live promotion list from ERPNext. "
			"Use the POS Promotion list in ERPNext for the full active promotion report.</p>"
		),
	},
	{
		"title": "How do I set up a promotion in Modern POS?",
		"question": "How to configure discount or offer for POS checkout?",
		"keywords": "promotion, discount, offer, campaign, setup, configure, modern pos, erpnext",
		"category": "Promotions",
		"module_area": "Modern POS",
		"sort_order": 30,
		"answer": (
			"<p>Create the promotion in ERPNext (promotion master / pricing rule per your setup), assign it to the store, item, or customer group, then sync Modern POS.</p>"
			"<p>After sync, the promotion applies at checkout based on item, quantity, date range, or customer group rules.</p>"
		),
	},
	{
		"title": "Promotion not applying at checkout",
		"question": "Discount or offer not working on POS",
		"keywords": "promotion, discount, not applying, offer, checkout, sync, modern pos",
		"category": "Promotions",
		"module_area": "Modern POS",
		"sort_order": 31,
		"answer": (
			"<p>Check promotion start/end dates, eligible items, store assignment, and customer group. Sync Modern POS after changes.</p>"
			"<p>If the terminal was offline, promotions active only on server may not apply until sync completes.</p>"
		),
	},
	{
		"title": "How to apply manual discount on POS",
		"question": "Cashier needs line or bill discount at checkout",
		"keywords": "manual discount, line discount, bill discount, override, manager approval, pos",
		"category": "Promotions",
		"module_area": "Modern POS",
		"sort_order": 32,
		"answer": (
			"<p>Use the discount action on the line or total bill as allowed by your role. Some sites require manager PIN or supervisor login for overrides.</p>"
			"<p>If discount options are missing, check POS Profile permissions and Modern POS role settings.</p>"
		),
	},
	{
		"title": "Loyalty points not applying at checkout",
		"question": "Customer loyalty points not earned or redeemed on POS",
		"keywords": "loyalty, points, rewards, checkout, customer, redeem, earn, modern pos",
		"category": "Loyalty",
		"module_area": "Modern POS",
		"sort_order": 40,
		"answer": (
			"<p>Identify the customer on the sale, confirm the loyalty program is active for the store, and sync Modern POS.</p>"
			"<p>Points usually apply after customer lookup (mobile, card, or customer code). Offline sales may update loyalty only after sync.</p>"
		),
	},
	{
		"title": "How to set up loyalty program",
		"question": "How do I configure customer loyalty for retail?",
		"keywords": "loyalty program, setup, configure, points, rewards, customer, erpnext, modern pos",
		"category": "Loyalty",
		"module_area": "ERPNext",
		"sort_order": 41,
		"answer": (
			"<p>Configure loyalty rules in ERPNext per your Printechs setup (program, earn/redeem rules, customer groups), assign to company/store, then sync Modern POS.</p>"
			"<p>Test with a sample customer before go-live and verify earn on sale and redeem at checkout.</p>"
		),
	},
	{
		"title": "How to redeem loyalty points on POS",
		"question": "Customer wants to pay using loyalty points",
		"keywords": "redeem, loyalty, points, payment, checkout, customer, modern pos",
		"category": "Loyalty",
		"module_area": "Modern POS",
		"sort_order": 42,
		"answer": (
			"<p>Look up the customer, check available points balance, and use the loyalty redeem option at payment if enabled for your store.</p>"
			"<p>Redemption limits and minimum bill rules depend on your loyalty configuration in ERPNext.</p>"
		),
	},
	{
		"title": "E-wallet balance not updating",
		"question": "Customer wallet balance wrong on POS",
		"keywords": "ewallet, e-wallet, wallet, balance, top up, payment, modern pos, sync",
		"category": "E-Wallet",
		"module_area": "Modern POS",
		"sort_order": 50,
		"answer": (
			"<p>Verify wallet top-ups posted in ERPNext, customer is identified on POS, and terminal has synced recently.</p>"
			"<p>Offline sales may show stale wallet balance until sync. Check pending wallet transactions and retry sync.</p>"
		),
	},
	{
		"title": "How to top up customer e-wallet",
		"question": "How do I add wallet balance for a customer?",
		"keywords": "ewallet, e-wallet, wallet, top up, recharge, balance, customer, erpnext",
		"category": "E-Wallet",
		"module_area": "ERPNext",
		"sort_order": 51,
		"answer": (
			"<p>Create the wallet top-up entry in ERPNext using your configured wallet DocType or payment workflow, submit it, then sync Modern POS.</p>"
			"<p>Confirm the customer record matches the one used at checkout.</p>"
		),
	},
	{
		"title": "Barcode scanner not working on POS",
		"question": "Scanner not reading barcodes on Modern POS",
		"keywords": "barcode, scanner, scan, keyboard, enter, usb, modern pos, troubleshooting",
		"category": "Troubleshooting",
		"module_area": "Modern POS",
		"sort_order": 60,
		"answer": (
			"<p>Set scanner to keyboard mode, focus the barcode field, and ensure Enter is sent after each scan. Test in Notepad first.</p>"
			"<p>Restart Modern POS, try another USB port, and verify item barcodes exist in ERPNext after sync.</p>"
		),
	},
	{
		"title": "Receipt printer not printing",
		"question": "POS receipt printer not working",
		"keywords": "receipt, printer, print, thermal, invoice, troubleshooting, modern pos",
		"category": "Troubleshooting",
		"module_area": "Modern POS",
		"sort_order": 61,
		"answer": (
			"<p>Check printer power, paper, USB/network connection, and default printer in POS settings.</p>"
			"<p>Reprint from last invoice if available. For network printers, confirm IP and that the terminal can reach the printer.</p>"
		),
	},
	{
		"title": "Payment mode not showing on POS",
		"question": "Cash or card payment option missing at checkout",
		"keywords": "payment mode, cash, card, checkout, missing, pos profile, modern pos",
		"category": "Troubleshooting",
		"module_area": "Modern POS",
		"sort_order": 62,
		"answer": (
			"<p>Payment modes come from <strong>POS Profile</strong>. Add the mode of payment there, save, and sync Modern POS.</p>"
			"<p>Role restrictions may hide certain modes for cashiers.</p>"
		),
	},
	{
		"title": "How to add a payment type in Modern POS",
		"question": "How do I add a new payment type or mode of payment in Modern POS?",
		"keywords": "payment type, payment mode, mode of payment, add payment, new payment, cash, card, mop, pos profile, modern pos, checkout",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 7,
		"answer": (
			"<p><strong>Add a payment type for Modern POS</strong></p>"
			"<ol>"
			"<li><strong>Mode of Payment</strong> — In ERPNext, open or create <strong>Mode of Payment</strong> "
			"(for example Cash, Card, Wallet) and link the correct account if required.</li>"
			"<li><strong>POS Profile</strong> — Open your store <strong>POS Profile</strong> and add the mode under "
			"<strong>Payment Methods</strong> / allowed payment modes.</li>"
			"<li><strong>Save &amp; sync</strong> — Save the POS Profile, then run <strong>Sync</strong> on the Modern POS terminal "
			"or store profile so the new payment type appears at checkout.</li>"
			"<li><strong>Test</strong> — Start a sale and confirm the new payment option is available at payment screen.</li>"
			"</ol>"
			"<p>If the mode still does not appear, check cashier role permissions and that the POS Profile linked to the terminal includes that payment mode.</p>"
		),
	},
	{
		"title": "Wrong stock quantity on POS",
		"question": "POS shows incorrect available quantity",
		"keywords": "stock, quantity, inventory, wrong, available, sync, warehouse, modern pos",
		"category": "Troubleshooting",
		"module_area": "Modern POS",
		"sort_order": 63,
		"answer": (
			"<p>Compare ERPNext Stock Balance for the POS warehouse, then sync Modern POS.</p>"
			"<p>Pending transfers, unsubmitted stock entries, or offline sales not yet uploaded can cause temporary differences.</p>"
		),
	},
	{
		"title": "How to process return or refund on POS",
		"question": "Customer returning items or requesting refund",
		"keywords": "return, refund, credit note, exchange, reverse sale, modern pos",
		"category": "Modern POS",
		"module_area": "Modern POS",
		"sort_order": 64,
		"answer": (
			"<p>Use the return/refund function in Modern POS, reference the original invoice when required, and select return reason.</p>"
			"<p>Manager approval may be required. Returned stock and refund payment modes post to ERPNext after sync/submit per your setup.</p>"
		),
	},
	{
		"title": "Customer not found at checkout",
		"question": "Cannot search customer on POS",
		"keywords": "customer, not found, search, lookup, mobile, loyalty, modern pos, sync",
		"category": "Troubleshooting",
		"module_area": "Modern POS",
		"sort_order": 65,
		"answer": (
			"<p>Confirm the customer exists in ERPNext, is enabled for the company/store, and master data has synced.</p>"
			"<p>Search by mobile, name, or customer ID. Offline mode may only find customers cached on the terminal.</p>"
		),
	},
	{
		"title": "How do I create a support ticket?",
		"question": "I need help from Printechs support team",
		"keywords": "support ticket, create ticket, portal, help, request, case",
		"category": "General",
		"module_area": "Support",
		"sort_order": 70,
		"answer": (
			"<p>Sign in to the Printechs Support Portal, open <strong>Tickets</strong>, click <strong>New Ticket</strong>, "
			"select ticket type, enter subject and details, then submit.</p>"
			"<p>You can also ask PRAI here and click <strong>Create ticket</strong> to escalate with the chat transcript.</p>"
		),
	},
	{
		"title": "How to reply to a support ticket",
		"question": "Technician asked for more information on my ticket",
		"keywords": "reply, respond, comment, support ticket, portal, technician, customer",
		"category": "General",
		"module_area": "Support",
		"sort_order": 71,
		"answer": (
			"<p>Open the ticket in the Support Portal, read the latest message, add your reply in the communication panel, and submit.</p>"
			"<p>Attach screenshots or files if the technician requested them.</p>"
		),
	},
	{
		"title": "How to check support ticket status",
		"question": "Where do I see if my ticket is open or resolved?",
		"keywords": "ticket status, open, resolved, closed, waiting, portal, support",
		"category": "General",
		"module_area": "Support",
		"sort_order": 72,
		"answer": (
			"<p>Open <strong>Tickets</strong> in the Support Portal. Status shows on the list and ticket detail page "
			"(Open, In Progress, Waiting for Customer, Resolved, Closed).</p>"
			"<p>You'll receive email updates when the support team replies if email is configured on your account.</p>"
		),
	},
	{
		"title": "How to upload files to a support ticket",
		"question": "Attach screenshot or document to ticket",
		"keywords": "upload, attachment, file, screenshot, support ticket, portal",
		"category": "General",
		"module_area": "Support",
		"sort_order": 73,
		"answer": (
			"<p>Open the ticket detail page in the portal and use the attachments or communication panel upload option.</p>"
			"<p>Add a short comment describing what the file shows to help the technician respond faster.</p>"
		),
	},
	{
		"title": "How to view sales report from POS",
		"question": "Where are POS sales and end of day reports?",
		"keywords": "sales report, pos sales, end of day, z report, analytics, erpnext, modern pos",
		"category": "General",
		"module_area": "ERPNext",
		"sort_order": 80,
		"answer": (
			"<p>Submitted POS invoices appear in ERPNext sales reports. Use POS Register, Sales Register, or your configured retail dashboards.</p>"
			"<p>Shift close summary in Modern POS gives cashier-level totals before ERPNext consolidation.</p>"
		),
	},
]


def seed_prai_faqs(*, update_existing: bool = False) -> dict:
	"""Insert (or optionally update) catalog FAQs. Safe to run multiple times."""
	created = 0
	updated = 0
	skipped = 0
	for item in PRAI_FAQ_CATALOG:
		title = item["title"]
		existing = frappe.db.get_value("PRAI FAQ", {"title": title}, "name")
		if existing:
			if update_existing:
				doc = frappe.get_doc("PRAI FAQ", existing)
				for key in ("question", "answer", "keywords", "category", "module_area", "sort_order"):
					if key in item:
						doc.set(key, item[key])
				doc.is_active = 1
				doc.save(ignore_permissions=True)
				updated += 1
			else:
				skipped += 1
			continue
		doc = frappe.get_doc({"doctype": "PRAI FAQ", **item, "is_active": 1})
		doc.insert(ignore_permissions=True)
		created += 1
	return {"created": created, "updated": updated, "skipped": skipped, "total": len(PRAI_FAQ_CATALOG)}


def import_faq_pack(*, update_existing: bool = True) -> dict:
	"""Import optional extra FAQs from prai_faq_import_pack.json (safe to run multiple times)."""
	import json
	from pathlib import Path

	path = Path(__file__).with_name("prai_faq_import_pack.json")
	if not path.exists():
		return {"created": 0, "updated": 0, "skipped": 0, "total": 0, "error": "pack file not found"}
	items = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(items, list):
		frappe.throw("Invalid FAQ import pack format.")
	from printechs_support.printechs_support_system.prai_document_import import upsert_prai_faqs

	return upsert_prai_faqs(items, update_existing=update_existing)
