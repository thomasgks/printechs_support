from urllib.parse import unquote

import frappe

from printechs_support.api.help_article import get_help_articles, public_categories
from printechs_support.www.help_article import get_help_brand_context


def get_context(context):
	context.no_cache = 1
	context.title = "Help Center"
	path = getattr(frappe.local.request, "path", "") or ""
	category = ""
	if path.startswith("/help-center/"):
		category = unquote(path.replace("/help-center/", "", 1)).strip("/")
	module_area = (frappe.form_dict.get("module_area") or "").strip()
	search = (frappe.form_dict.get("search") or "").strip()

	result = get_help_articles(
		module_area=module_area or None,
		category=category or None,
		search=search or None,
		customer_view=1,
		limit=100,
	)
	context.categories = public_categories(module_area=module_area or None)
	context.articles = result.get("articles") or []
	context.selected_category = category
	context.selected_module_area = module_area
	context.search = search
	context.module_areas = [
		"Support",
		"WMS",
		"ERPNext",
		"Sales",
		"Purchase",
		"Stock",
		"Accounts",
		"HR",
		"General",
	]
	context.update(get_help_brand_context())
