# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint, sanitize_html

from printechs_support.printechs_support_system.prai_document_import import (
	generate_faq_items_from_text,
	preview_import_lines,
)
from printechs_support.prai_studio.source_analyzer_service import build_analysis_summary

MAX_OPENAI_SOURCE_CHARS = 20_000


def generate_draft_faqs_from_findings(
	findings: list[dict],
	*,
	default_category: str,
	default_module_area: str,
	use_openai: bool,
	product_name: str = "Modern POS",
) -> list[dict]:
	"""Build draft FAQ rows from analyzer findings (basic + optional OpenAI enrichment)."""
	basic_items = _generate_basic_faqs_from_findings(
		findings,
		default_category=default_category,
		default_module_area=default_module_area,
		product_name=product_name,
	)
	if not use_openai:
		return basic_items

	analysis_text = build_analysis_summary(findings)
	excerpt_blob = _build_source_excerpt_blob(findings)
	combined = f"{analysis_text}\n\nSource excerpts:\n{excerpt_blob}"[:MAX_OPENAI_SOURCE_CHARS]
	try:
		openai_items = generate_faq_items_from_text(
			combined,
			default_category=default_category,
			default_module_area=default_module_area,
			use_openai=True,
		)
	except Exception:
		frappe.log_error(title="PRAI Studio OpenAI FAQ generation", message=frappe.get_traceback())
		if basic_items:
			return basic_items
		raise

	merged = _merge_faq_items(basic_items, openai_items)
	return merged or basic_items


def draft_lines_from_faq_items(items: list[dict]) -> list[dict]:
	preview = preview_import_lines(items)
	lines: list[dict] = []
	for row in preview:
		lines.append(
			{
				"include": row.get("include", 1),
				"review_status": "Draft",
				"action": row.get("action") or "Create",
				"title": row.get("title"),
				"question": row.get("question"),
				"keywords": row.get("keywords"),
				"answer": row.get("answer"),
				"category": row.get("category"),
				"module_area": row.get("module_area"),
				"source_finding": row.get("source_finding") or "",
				"prai_faq": row.get("prai_faq") or "",
			}
		)
	return lines


def _generate_basic_faqs_from_findings(
	findings: list[dict],
	*,
	default_category: str,
	default_module_area: str,
	product_name: str,
) -> list[dict]:
	items: list[dict] = []
	seen_titles: set[str] = set()

	for row in findings:
		finding_type = row.get("finding_type") or "Source"
		title_base = (row.get("title") or "").strip()
		file_name = (row.get("file_path") or "").split("/")[-1]
		if not title_base:
			continue

		category = _category_for_finding(row, default_category)
		module_area = _module_area_for_finding(row, default_module_area)

		if finding_type == "Promotion" and "Feature class:" in title_base:
			class_name = title_base.split("Feature class:", 1)[-1].strip()
			title = f"How does {class_name} work in {product_name}?"
			answer = _format_answer(
				f"{class_name} is implemented in source file {file_name}.",
				[
					f"Review class {class_name} in {row.get('file_path')}.",
					"Map fields and validation rules to ERPNext POS Promotion setup.",
					"Test the feature on a Modern POS terminal after configuration.",
				],
				row.get("detail") or row.get("summary"),
			)
			_add_item(items, seen_titles, title, title, f"{class_name}, promotion, modern pos, {file_name}", answer, category, module_area, row)
			continue

		if finding_type == "Database" and title_base.startswith("Database table:"):
			table = title_base.split(":", 1)[-1].strip()
			title = f"What is the {table} table used for in {product_name}?"
			answer = _format_answer(
				f"The `{table}` table is referenced in SQL script {file_name}.",
				[
					f"Inspect {row.get('file_path')} for schema and relationships.",
					"Confirm matching DocTypes or custom tables in ERPNext if synced.",
				],
				row.get("summary"),
			)
			_add_item(items, seen_titles, title, title, f"{table}, database, sql, modern pos", answer, category, module_area, row)
			continue

		if finding_type == "Documentation" and title_base.startswith("Doc topic:"):
			topic = title_base.split(":", 1)[-1].strip()
			title = f"{topic} — {product_name} guide"
			answer = _format_answer(
				f"Documentation topic extracted from {file_name}.",
				[_line for _line in (row.get("detail") or row.get("summary") or "").splitlines()[:8] if _line.strip()],
			)
			_add_item(items, seen_titles, title, topic, f"{topic}, documentation, modern pos", answer, "General", module_area, row)
			continue

		if finding_type in {"Promotion", "Form", "Api"} and "file:" in title_base.lower():
			title = f"What is covered in {file_name} ({finding_type})?"
			answer = _format_answer(
				row.get("summary") or f"{finding_type} source file in Modern POS codebase.",
				[
					f"Open {row.get('file_path')} in the extracted source tree.",
					"Use this file to understand UI flow, API endpoints, or promotion logic.",
				],
				row.get("detail"),
			)
			keywords = f"{finding_type.lower()}, {file_name}, modern pos, source code"
			_add_item(items, seen_titles, title, title, keywords, answer, category, module_area, row)

	if not items and findings:
		title = f"Overview of scanned {product_name} source modules"
		summary_lines = [f"- {row.get('title')} ({row.get('file_path')})" for row in findings[:20]]
		answer = _format_answer(
			f"PRAI Studio analyzed {len(findings)} finding(s) from uploaded source.",
			summary_lines,
		)
		_add_item(
			items,
			seen_titles,
			title,
			title,
			f"modern pos, source, overview, {product_name.lower()}",
			answer,
			default_category,
			default_module_area,
			findings[0],
		)
	return items[:60]


def _add_item(
	items: list[dict],
	seen_titles: set[str],
	title: str,
	question: str,
	keywords: str,
	answer: str,
	category: str,
	module_area: str,
	row: dict,
) -> None:
	title = re.sub(r"\s+", " ", title).strip()[:140]
	if not title or title.lower() in seen_titles:
		return
	seen_titles.add(title.lower())
	items.append(
		{
			"title": title,
			"question": question[:500],
			"keywords": keywords[:500],
			"answer": sanitize_html(answer),
			"category": category,
			"module_area": module_area,
			"source_finding": row.get("title") or "",
		}
	)


def _format_answer(intro: str, steps: list[str], extra: str | None = None) -> str:
	step_items = []
	for step in steps:
		clean = re.sub(r"^\d+[\.)]\s*", "", (step or "").strip())
		clean = re.sub(r"^[-•]\s*", "", clean).strip()
		if clean:
			step_items.append(f"<li>{sanitize_html(clean)}</li>")
	body = f"<p>{sanitize_html(intro)}</p>"
	if step_items:
		body += f"<ol>{''.join(step_items)}</ol>"
	if extra:
		extra_clean = sanitize_html(extra[:1500]).replace("\n", "<br>")
		body += f"<p><em>Source excerpt:</em><br>{extra_clean}</p>"
	return body


def _category_for_finding(row: dict, default: str) -> str:
	finding_type = row.get("finding_type") or ""
	if finding_type == "Promotion":
		return "Promotions"
	if finding_type == "Database":
		return "ERPNext"
	return default


def _module_area_for_finding(row: dict, default: str) -> str:
	if (row.get("finding_type") or "") in {"Promotion", "Form", "Api", "Source"}:
		return "Modern POS"
	return default


def _build_source_excerpt_blob(findings: list[dict], limit: int = MAX_OPENAI_SOURCE_CHARS) -> str:
	parts: list[str] = []
	size = 0
	for row in findings:
		chunk = f"\n--- {row.get('title')} ({row.get('file_path')}) ---\n"
		chunk += (row.get("detail") or row.get("summary") or "")[:1200]
		if size + len(chunk) > limit:
			break
		parts.append(chunk)
		size += len(chunk)
	return "".join(parts)


def _merge_faq_items(basic: list[dict], openai_items: list[dict]) -> list[dict]:
	merged: list[dict] = []
	seen: set[str] = set()
	for row in basic + openai_items:
		title = (row.get("title") or "").strip().lower()
		if not title or title in seen:
			continue
		seen.add(title)
		merged.append(row)
	return merged[:80]
