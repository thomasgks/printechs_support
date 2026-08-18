# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json
import os
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, get_files_path, now_datetime

from printechs_support.printechs_support_system.prai_document_import import upsert_prai_faqs
from printechs_support.prai_studio.help_article_generation_service import upsert_help_articles


def publish_approved_knowledge(knowledge_run_name: str) -> dict:
	"""Publish approved draft FAQ and Help Article rows to live PRAI knowledge."""
	run = frappe.get_doc("PRAI Studio Knowledge Run", knowledge_run_name)
	faq_items = _selected_faq_items(run)
	help_items = _selected_help_items(run)
	if not faq_items and not help_items:
		frappe.throw(_("Approve at least one draft FAQ or Help Article row before publishing."), frappe.ValidationError)

	faq_result = upsert_prai_faqs(faq_items, update_existing=cint(run.update_existing)) if faq_items else {
		"created": 0,
		"updated": 0,
		"skipped": 0,
	}
	help_result = (
		upsert_help_articles(help_items, update_existing=cint(run.update_existing_help))
		if help_items
		else {"created": 0, "updated": 0, "skipped": 0}
	)

	package_url = _write_publish_package(run, faq_items, help_items, faq_result, help_result)
	publish_log = frappe.get_doc(
		{
			"doctype": "PRAI Publish Log",
			"title": f"{run.source_project} — {frappe.utils.format_datetime(now_datetime())}",
			"status": "Published",
			"source_project": run.source_project,
			"knowledge_run": run.name,
			"source_scan_run": run.source_scan_run,
			"published_by": frappe.session.user,
			"published_date": now_datetime(),
			"item_count": len(faq_items),
			"help_article_count": len(help_items),
			"package_file": package_url,
			"publish_log": _format_publish_log(faq_result, help_result, faq_items, help_items),
		}
	)
	publish_log.insert(ignore_permissions=True)

	for row in run.draft_items or []:
		if not cint(row.include) or (row.review_status or "") != "Approved":
			continue
		existing = frappe.db.get_value("PRAI FAQ", {"title": row.title}, "name")
		if existing:
			row.prai_faq = existing

	for row in run.draft_help_items or []:
		if not cint(row.include) or (row.review_status or "") != "Approved":
			continue
		existing = frappe.db.get_value(
			"Help Article", {"title": row.title, "category": row.help_category}, "name"
		)
		if existing:
			row.help_article = existing

	run.status = "Published"
	run.latest_publish_log = publish_log.name
	run.generation_log = (run.generation_log or "") + "\n" + publish_log.publish_log
	run.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"success": True,
		"status": run.status,
		"publish_log": publish_log.name,
		"faq_created": faq_result.get("created", 0),
		"faq_updated": faq_result.get("updated", 0),
		"help_created": help_result.get("created", 0),
		"help_updated": help_result.get("updated", 0),
	}


def publish_approved_faqs(knowledge_run_name: str) -> dict:
	"""Backward-compatible alias used by Phase 2 callers."""
	return publish_approved_knowledge(knowledge_run_name)


def _selected_faq_items(run) -> list[dict]:
	selected = []
	for row in run.draft_items or []:
		if not cint(row.include):
			continue
		if (row.review_status or "") != "Approved":
			continue
		if not (row.title or "").strip() or not (row.answer or "").strip():
			continue
		selected.append(
			{
				"title": row.title,
				"question": row.question or row.title,
				"keywords": row.keywords or "",
				"answer": row.answer,
				"category": row.category or run.default_category or "General",
				"module_area": row.module_area or run.default_module_area or "General",
			}
		)
	return selected


def _selected_help_items(run) -> list[dict]:
	selected = []
	for row in run.draft_help_items or []:
		if not cint(row.include):
			continue
		if (row.review_status or "") != "Approved":
			continue
		if not (row.title or "").strip() or not (row.content or "").strip():
			continue
		selected.append(
			{
				"title": row.title,
				"summary": row.summary or "",
				"keywords": row.keywords or "",
				"content": row.content,
				"help_category": row.help_category,
				"module_area": row.module_area or run.default_module_area or "ERPNext",
			}
		)
	return selected


def _format_publish_log(faq_result: dict, help_result: dict, faq_items: list, help_items: list) -> str:
	lines = [
		_("Published {0} FAQ(s) and {1} Help Article(s) to live PRAI Agent.").format(
			len(faq_items), len(help_items)
		),
		_("FAQs — created: {0}, updated: {1}, skipped: {2}").format(
			faq_result.get("created", 0),
			faq_result.get("updated", 0),
			faq_result.get("skipped", 0),
		),
		_("Help Articles — created: {0}, updated: {1}, skipped: {2}").format(
			help_result.get("created", 0),
			help_result.get("updated", 0),
			help_result.get("skipped", 0),
		),
	]
	for item in faq_items[:10]:
		lines.append(f"- FAQ: {item['title']}")
	for item in help_items[:10]:
		lines.append(f"- Help: {item['title']}")
	return "\n".join(lines)


def _write_publish_package(
	run, faq_items: list[dict], help_items: list[dict], faq_result: dict, help_result: dict
) -> str:
	payload = {
		"version": 2,
		"published_at": datetime.utcnow().isoformat() + "Z",
		"source_project": run.source_project,
		"source_scan_run": run.source_scan_run,
		"knowledge_run": run.name,
		"product_name": run.product_name,
		"product_version": run.product_version,
		"faqs": faq_items,
		"help_articles": help_items,
		"stats": {"faqs": faq_result, "help_articles": help_result},
	}
	filename = f"prai_studio_package_{run.name.replace('/', '_')}.json"
	target_dir = get_files_path(is_private=1)
	os.makedirs(target_dir, exist_ok=True)
	target_path = os.path.join(target_dir, filename)
	with open(target_path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle, indent=2, ensure_ascii=False)
	return f"/private/files/{filename}"
