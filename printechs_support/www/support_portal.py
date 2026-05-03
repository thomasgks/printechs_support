# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Context for www/support-portal.html (standalone portal shell)."""

import re
from pathlib import Path

import frappe


def get_context(context):
	context.title = context.get("title") or "Support Portal"
	existing = (context.get("body_class") or "").strip()
	context.body_class = f"{existing} printechs-portal-standalone".strip()
	_set_portal_assets_from_build(context)
	return context


def _set_portal_assets_from_build(context):
	"""Read hashed JS/CSS URLs from the Vite build (public/portal/index.html).

	Avoids relying on templates/includes/portal_react_bundle.html: if that include is
	missing on the server, Jinja raises TemplateNotFoundError → HTTP 417 in Frappe.
	"""
	app_path = Path(frappe.get_app_path("printechs_support"))
	index_html = app_path / "public" / "portal" / "index.html"
	if not index_html.is_file():
		return

	raw = index_html.read_text(encoding="utf-8")
	# Attribute order matches Vite output; allow multiline tags.
	m_js = re.search(
		r'<script[^>]+type\s*=\s*["\']module["\'][^>]+src\s*=\s*["\']([^"\']+)["\']',
		raw,
		re.IGNORECASE | re.DOTALL,
	)
	if not m_js:
		m_js = re.search(
			r'<script[^>]+src\s*=\s*["\']([^"\']+)["\'][^>]+type\s*=\s*["\']module["\']',
			raw,
			re.IGNORECASE | re.DOTALL,
		)
	m_css = re.search(
		r'<link[^>]+rel\s*=\s*["\']stylesheet["\'][^>]+href\s*=\s*["\']([^"\']+)["\']',
		raw,
		re.IGNORECASE | re.DOTALL,
	)
	if not m_css:
		m_css = re.search(
			r'<link[^>]+href\s*=\s*["\']([^"\']+)["\'][^>]+rel\s*=\s*["\']stylesheet["\']',
			raw,
			re.IGNORECASE | re.DOTALL,
		)
	if m_js and m_css:
		context.portal_js_url = m_js.group(1).strip()
		context.portal_css_url = m_css.group(1).strip()
