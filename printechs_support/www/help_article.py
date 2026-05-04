from urllib.parse import unquote

import frappe

from printechs_support.api.help_article import get_help_article_detail


def get_help_brand_context():
	logo = ""
	try:
		from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

		logo = get_app_logo() or ""
	except Exception:
		logo = ""
	brand_name = (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_system_settings("app_name")
		or "Printechs Support"
	)
	return {"brand_logo": logo, "brand_name": brand_name}


def get_context(context):
	context.no_cache = 1
	path = getattr(frappe.local.request, "path", "") or ""
	name = ""
	if path.startswith("/help-article/"):
		name = unquote(path.replace("/help-article/", "", 1)).strip("/")
	result = get_help_article_detail(name=name, customer_view=1)
	context.article = result.get("article") or {}
	context.title = context.article.get("title") or "Help Article"
	context.update(get_help_brand_context())
