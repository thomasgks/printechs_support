# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Support Ticket Notification emails: send immediately (no scheduler flush wait)."""

import frappe
from frappe.email.doctype.notification.notification import Notification as FrappeNotification


class PrintechsSupportNotification(FrappeNotification):
	def send_an_email(self, doc, context):
		if self.document_type != "Support Ticket" or self.channel != "Email":
			return super().send_an_email(doc, context)

		real_sendmail = frappe.sendmail

		def sendmail_immediate(*args, **kwargs):
			kwargs["delayed"] = False
			return real_sendmail(*args, **kwargs)

		frappe.sendmail = sendmail_immediate
		try:
			return super().send_an_email(doc, context)
		finally:
			frappe.sendmail = real_sendmail
