# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

from html import escape as html_escape

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, sanitize_html, strip_html

from printechs_support.permissions import user_sees_all_support_records


def _as_bool(value) -> bool:
	return bool(cint(value))


def _is_internal_user() -> bool:
	user = frappe.session.user
	if not user or user == "Guest":
		return False
	return user_sees_all_support_records(user) or frappe.has_permission("Help Article", "write")


def _public_filters() -> dict:
	return {"is_published": 1, "show_in_portal": 1, "allow_customer_view": 1}


def _desk_filters() -> dict:
	return {"is_published": 1, "show_in_desk": 1}


def _base_filters(customer_view=0) -> dict:
	if frappe.session.user == "Guest" or _as_bool(customer_view) or not _is_internal_user():
		return _public_filters()
	return _desk_filters()


def _apply_optional_filters(filters: dict, *, module_area=None, related_doctype=None, category=None):
	if module_area:
		filters["module_area"] = module_area
	if related_doctype:
		filters["related_doctype"] = related_doctype
	if category:
		filters["category"] = category


def _search_or_filters(search: str | None) -> list[list[str]]:
	search = (search or "").strip()
	if not search:
		return []
	like = f"%{search}%"
	return [
		["Help Article", "title", "like", like],
		["Help Article", "summary", "like", like],
		["Help Article", "keywords", "like", like],
		["Help Article", "content", "like", like],
	]


def _article_summary(row) -> dict:
	return {
		"name": row.name,
		"title": row.title,
		"summary": row.summary or "",
		"category": row.category,
		"module_area": row.module_area or "",
		"related_doctype": row.related_doctype or "",
		"video_url": row.video_url or "",
		"has_video": bool(row.video_url or row.video_embed_html),
		"attachments_count": cint(row.attachments_count),
	}


def _attach_counts(rows) -> None:
	names = [row.name for row in rows if row.name]
	if not names:
		return
	counts = {
		row.parent: cint(row.count)
		for row in frappe.db.sql(
			"""
			SELECT parent, COUNT(*) AS count
			FROM `tabHelp Article Attachment`
			WHERE parent IN %(names)s
			GROUP BY parent
			""",
			{"names": names},
			as_dict=True,
		)
	}
	for row in rows:
		row.attachments_count = counts.get(row.name, 0)


@frappe.whitelist(allow_guest=True)
def get_help_articles(
	module_area=None,
	related_doctype=None,
	category=None,
	search=None,
	customer_view=0,
	limit=20,
):
	"""Return published help articles for desk, portal, website, and external clients."""
	filters = _base_filters(customer_view)
	_apply_optional_filters(filters, module_area=module_area, related_doctype=related_doctype, category=category)
	rows = frappe.get_all(
		"Help Article",
		filters=filters,
		or_filters=_search_or_filters(search),
		fields=[
			"name",
			"title",
			"summary",
			"category",
			"module_area",
			"related_doctype",
			"video_url",
			"video_embed_html",
			"sort_order",
			"modified",
		],
		order_by="sort_order asc, modified desc",
		limit_page_length=max(min(cint(limit) or 20, 100), 1),
	)
	_attach_counts(rows)
	return {"success": True, "articles": [_article_summary(row) for row in rows]}


def _can_view_article(doc, customer_view=0) -> bool:
	if not cint(doc.is_published):
		return False
	if frappe.session.user == "Guest" or _as_bool(customer_view) or not _is_internal_user():
		return bool(cint(doc.show_in_portal) and cint(doc.allow_customer_view))
	return bool(cint(doc.show_in_desk))


def _attachment_rows(doc) -> list[dict]:
	out = []
	for row in doc.attachments or []:
		href = row.file or row.external_url or ""
		lower_href = href.lower().split("?", 1)[0]
		out.append(
			{
				"attachment_title": row.attachment_title or "",
				"file": row.file or "",
				"external_url": row.external_url or "",
				"description": sanitize_html(row.description or ""),
				"is_image": lower_href.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")),
				"is_pdf": lower_href.endswith(".pdf"),
			}
		)
	return out


@frappe.whitelist(allow_guest=True)
def get_help_article_detail(name=None, customer_view=0):
	"""Return a full help article and increment its view counter."""
	name = (name or "").strip()
	if not name or not frappe.db.exists("Help Article", name):
		frappe.throw(_("Help article not found."), frappe.DoesNotExistError)
	doc = frappe.get_doc("Help Article", name)
	if not _can_view_article(doc, customer_view):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	frappe.db.sql(
		"""
		UPDATE `tabHelp Article`
		SET view_count = IFNULL(view_count, 0) + 1,
		    last_viewed_on = %s
		WHERE name = %s
		""",
		(now_datetime(), doc.name),
	)
	doc.view_count = cint(doc.view_count) + 1
	doc.last_viewed_on = now_datetime()

	return {
		"success": True,
		"article": {
			"name": doc.name,
			"title": doc.title,
			"summary": doc.summary or "",
			"category": doc.category,
			"module_area": doc.module_area or "",
			"related_doctype": doc.related_doctype or "",
			"related_issue_type": doc.related_issue_type or "",
			"keywords": doc.keywords or "",
			"content": sanitize_html(doc.content or ""),
			"video_url": doc.video_url or "",
			"video_embed_html": doc.video_embed_html or "",
			"attachments": _attachment_rows(doc),
		},
	}


def _score_article(row, *, module_area=None, doctype=None, issue_type=None, screen=None, search=None) -> int:
	score = 0
	haystack = " ".join(
		str(x or "")
		for x in (
			row.title,
			row.summary,
			row.keywords,
			strip_html(row.content or ""),
			row.related_issue_type,
			row.module_area,
			row.related_doctype,
		)
	).lower()
	if doctype and row.related_doctype == doctype:
		score += 100
	if issue_type:
		needle = issue_type.lower()
		related = (row.related_issue_type or "").lower()
		if related == needle:
			score += 80
		elif needle in related or related in needle:
			score += 45
	if module_area and row.module_area == module_area:
		score += 30
	for term in (screen, search):
		for part in str(term or "").lower().split():
			if len(part) >= 2 and part in haystack:
				score += 8
	return score


@frappe.whitelist(allow_guest=True)
def get_contextual_help(module_area=None, doctype=None, screen=None, issue_type=None, search=None, customer_view=0, limit=10):
	"""Return best matching help articles for any module/screen."""
	filters = _base_filters(customer_view)
	if module_area:
		filters["module_area"] = module_area
	rows = frappe.get_all(
		"Help Article",
		filters=filters,
		or_filters=_search_or_filters(search or screen or issue_type),
		fields=[
			"name",
			"title",
			"summary",
			"category",
			"module_area",
			"related_doctype",
			"related_issue_type",
			"keywords",
			"content",
			"video_url",
			"video_embed_html",
			"sort_order",
			"modified",
		],
		order_by="sort_order asc, modified desc",
		limit_page_length=100,
	)
	_attach_counts(rows)
	scored = [
		(_score_article(row, module_area=module_area, doctype=doctype, issue_type=issue_type, screen=screen, search=search), row)
		for row in rows
	]
	scored.sort(key=lambda x: (-x[0], cint(x[1].sort_order), str(x[1].modified)), reverse=False)
	articles = [_article_summary(row) | {"score": score} for score, row in scored if score > 0]
	if not articles:
		articles = [_article_summary(row) | {"score": 0} for _, row in scored[: max(cint(limit) or 10, 1)]]
	return {"success": True, "articles": articles[: max(min(cint(limit) or 10, 50), 1)]}


def _assert_internal_create():
	if not _is_internal_user():
		frappe.throw(_("Only internal users can create help articles."), frappe.PermissionError)
	if not frappe.has_permission("Help Article", "create"):
		frappe.throw(_("You do not have permission to create Help Articles."), frappe.PermissionError)


@frappe.whitelist()
def create_help_article(**kwargs):
	"""Create a Help Article from desk/mobile tools."""
	_assert_internal_create()
	title = (kwargs.get("title") or "").strip()
	category = (kwargs.get("category") or "").strip()
	content = kwargs.get("content") or ""
	if not title or not category or not strip_html(content).strip():
		frappe.throw(_("Title, Category, and Content are required."), frappe.ValidationError)
	doc = frappe.get_doc(
		{
			"doctype": "Help Article",
			"title": title,
			"category": category,
			"module_area": kwargs.get("module_area") or "General",
			"related_doctype": kwargs.get("related_doctype"),
			"related_issue_type": kwargs.get("related_issue_type"),
			"summary": kwargs.get("summary"),
			"keywords": kwargs.get("keywords"),
			"content": sanitize_html(content),
			"video_url": kwargs.get("video_url"),
			"allow_customer_view": cint(kwargs.get("allow_customer_view")),
			"show_in_portal": cint(kwargs.get("show_in_portal", 1)),
			"show_in_desk": cint(kwargs.get("show_in_desk", 1)),
			"status": kwargs.get("status") or "Published",
		}
	)
	doc.insert()
	return {"success": True, "name": doc.name, "article_code": doc.article_code}


def public_categories(module_area=None) -> list[dict]:
	filters = {"is_active": 1}
	if module_area:
		filters["module_area"] = module_area
	return frappe.get_all(
		"Help Category",
		filters=filters,
		fields=["name", "category_name", "module_area", "description", "icon"],
		order_by="sort_order asc, category_name asc",
	)


def article_plain_preview(content: str, length: int = 180) -> str:
	text = strip_html(content or "").strip()
	if len(text) <= length:
		return text
	return text[: length - 1].rstrip() + "..."


def safe_html(value: str) -> str:
	return html_escape(value or "")


def publish_help_article_assets(name: str):
	"""Maintenance helper: convert local private files on a public article into public files."""
	doc = frappe.get_doc("Help Article", name)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"success": True, "attachments": _attachment_rows(doc)}
