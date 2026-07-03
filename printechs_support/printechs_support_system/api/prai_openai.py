# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.integrations.utils import make_post_request
from frappe.utils import cint, strip_html

from printechs_support.api.help_article import get_contextual_help
from printechs_support.permissions import user_sees_all_support_records
from printechs_support.printechs_support_system.doctype.printechs_support_settings.printechs_support_settings import (
	get_prai_openai_config,
)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_ESCALATE_RE = re.compile(r"\n*ESCALATE:\s*(yes|no)\s*$", re.IGNORECASE)


def is_openai_configured() -> bool:
	"""OpenAI enabled for FAQ Import and other server-side tools."""
	cfg = get_prai_openai_config()
	return bool(cfg.get("enabled") and cfg.get("api_key"))


def is_openai_chat_configured() -> bool:
	"""OpenAI enabled for portal chat answers."""
	cfg = get_prai_openai_config()
	return bool(cfg.get("enabled") and cfg.get("chat_enabled") and cfg.get("api_key"))


def _system_prompt() -> str:
	return (
		"You are PRAI (Printechs Retail AI Assistant) for Printechs customers and support portal users.\n"
		"Topics: Modern POS, ERPNext retail setup, promotions, stock, loyalty, e-wallet, troubleshooting, "
		"and Printechs Support Portal tickets.\n\n"
		"Response format (always follow this structure; plain text only, no markdown):\n"
		"Short topic title on the first line\n\n"
		"1. Step label — clear instruction\n"
		"2. Step label — clear instruction\n"
		"(add more numbered steps when helpful)\n\n"
		"Optional notes as bullet lines starting with •\n\n"
		"Rules:\n"
		"- Prefer the Knowledge context below. You may add standard ERPNext / retail POS concepts when they "
		"clearly help answer the question.\n"
		"- Do not invent Printechs-specific menu paths, custom field names, or company policies unless they "
		"appear in the context.\n"
		"- Be concise, professional, and procedural — like a support runbook.\n"
		"- If the question is outside retail/ERPNext/Printechs scope, say so briefly and recommend a "
		"support ticket.\n"
		"- End every reply with a final line exactly in this format: ESCALATE: yes OR ESCALATE: no\n"
		"  Use ESCALATE: yes only when human support is required or you cannot give a useful answer."
	)


def _normalize_chat_answer(text: str) -> str:
	"""Strip markdown noise so portal step formatting renders cleanly."""
	clean = (text or "").strip()
	clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
	clean = re.sub(r"`([^`]+)`", r"\1", clean)
	clean = re.sub(r"\n{3,}", "\n\n", clean)
	return clean.strip()


def _parse_model_reply(raw: str) -> tuple[str, bool]:
	text = (raw or "").strip()
	if not text:
		return "", True
	match = _ESCALATE_RE.search(text)
	if not match:
		return text, False
	suggest = match.group(1).lower() == "yes"
	content = _ESCALATE_RE.sub("", text).strip()
	return content, suggest


def _openai_error_message(exc: Exception) -> str:
	text = str(exc or "").strip()
	if "401" in text or "Incorrect API key" in text:
		return "invalid API key (401)"
	if "429" in text or "Too Many Requests" in text:
		return "rate limit or quota exceeded (429) — check OpenAI billing"
	if "404" in text and "model" in text.lower():
		return "model not found — check OpenAI Model in settings"
	if len(text) > 180:
		return text[:177] + "..."
	return text or "unknown error"


def _call_openai_chat(*, messages: list[dict], model: str, api_key: str, max_tokens: int = 900) -> str:
	payload = {
		"model": model,
		"messages": messages,
		"temperature": 0.2,
		"max_tokens": max_tokens,
	}
	try:
		response = make_post_request(
			OPENAI_CHAT_URL,
			headers={
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
			},
			json=payload,
		)
	except Exception as exc:
		raise frappe.ValidationError(_openai_error_message(exc)) from exc
	if not isinstance(response, dict):
		frappe.throw(_("Unexpected response from OpenAI."), frappe.ValidationError)
	choices = response.get("choices") or []
	if not choices:
		frappe.throw(_("OpenAI returned no choices."), frappe.ValidationError)
	message = choices[0].get("message") or {}
	content = (message.get("content") or "").strip()
	if not content:
		frappe.throw(_("OpenAI returned an empty answer."), frappe.ValidationError)
	return content


def build_knowledge_context(message: str, *, faq_rank_fn, help_match_fn) -> tuple[str, list[dict]]:
	"""Return context text and source metadata from near-match FAQs and help articles."""
	blocks: list[str] = []
	sources: list[dict] = []

	faq_matches = faq_rank_fn(message, limit=5)
	for score, row in faq_matches:
		answer = strip_html(row.answer or "").strip()
		if not answer:
			continue
		blocks.append(f"FAQ [{row.name}] {row.title}\n{answer[:1200]}")
		sources.append(
			{
				"type": "faq",
				"name": row.name,
				"title": row.title,
				"summary": answer[:180],
				"url": "",
				"score": score,
			}
		)

	customer_view = 1 if not user_sees_all_support_records(frappe.session.user) else 0
	help_result = get_contextual_help(search=message, customer_view=customer_view, limit=5)
	for article in help_result.get("articles") or []:
		title = article.get("title") or article.get("name") or "Help article"
		summary = (article.get("summary") or "").strip()
		name = article.get("name") or ""
		if not name and not summary:
			continue
		block = f"Help Article [{name}] {title}"
		if summary:
			block += f"\n{summary[:1200]}"
		blocks.append(block)
		sources.append(
			{
				"type": "help_article",
				"name": name,
				"title": title,
				"summary": summary[:180],
				"url": f"/help-center?article={name}" if name else "",
				"score": cint(article.get("score")),
			}
		)

	# Include explicit help matches from the main matcher when contextual search is sparse.
	for score, article in help_match_fn(message, limit=3):
		name = article.get("name") or ""
		if any(s.get("name") == name and s.get("type") == "help_article" for s in sources):
			continue
		title = article.get("title") or name or "Help article"
		summary = (article.get("summary") or "").strip()
		blocks.append(f"Help Article [{name}] {title}\n{summary[:1200]}")
		sources.append(
			{
				"type": "help_article",
				"name": name,
				"title": title,
				"summary": summary[:180],
				"url": f"/help-center?article={name}" if name else "",
				"score": score,
			}
		)

	context = "\n\n---\n\n".join(blocks).strip()
	if not context:
		context = "No matching FAQ or Help Center excerpts were found for this question."
	return context, sources[:8]


def _session_history(session, *, limit: int = 8) -> list[dict]:
	if not session:
		return []
	rows = list(session.messages or [])
	if len(rows) >= 1 and rows[-1].role == "User":
		rows = rows[:-1]
	out: list[dict] = []
	for row in rows[-limit:]:
		if row.role not in ("User", "Assistant"):
			continue
		out.append(
			{
				"role": "user" if row.role == "User" else "assistant",
				"content": row.content or "",
			}
		)
	return out


def ask_openai(
	question: str,
	*,
	session=None,
	knowledge_context: str,
	sources: list[dict] | None = None,
	faq_rank_fn=None,
	help_match_fn=None,
) -> tuple[str, list[dict], bool] | None:
	"""Call OpenAI with FAQ/Help context. Returns (answer, sources, suggest_escalation) or None if disabled."""
	if not is_openai_chat_configured():
		return None

	cfg = get_prai_openai_config()
	api_key = cfg.get("api_key")
	model = cfg.get("model") or "gpt-4o-mini"
	if not api_key:
		return None

	if faq_rank_fn and help_match_fn and not knowledge_context:
		knowledge_context, sources = build_knowledge_context(
			question,
			faq_rank_fn=faq_rank_fn,
			help_match_fn=help_match_fn,
		)

	messages: list[dict] = [{"role": "system", "content": _system_prompt()}]
	messages.append(
		{
			"role": "system",
			"content": f"Knowledge context:\n\n{knowledge_context}",
		}
	)
	for item in _session_history(session):
		messages.append(item)
	messages.append({"role": "user", "content": question})

	try:
		raw = _call_openai_chat(messages=messages, model=str(model), api_key=str(api_key))
	except frappe.ValidationError:
		raise
	except Exception as exc:
		frappe.log_error(title="PRAI OpenAI request failed", message=frappe.get_traceback())
		raise frappe.ValidationError(_openai_error_message(exc)) from exc

	content, suggest = _parse_model_reply(raw)
	content = _normalize_chat_answer(content)
	if not content:
		return None

	out_sources = list(sources or [])
	out_sources.append(
		{
			"type": "openai",
			"name": str(model),
			"title": "AI-assisted answer",
			"summary": "Generated using OpenAI with Printechs FAQ and Help Center context.",
			"url": "",
		}
	)
	return content, out_sources, suggest


def ask_openai_safe(
	question: str,
	*,
	session=None,
	knowledge_context: str = "",
	sources: list[dict] | None = None,
	faq_rank_fn=None,
	help_match_fn=None,
) -> tuple[tuple[str, list[dict], bool] | None, str]:
	"""Return ((answer, sources, suggest) or None, error_message)."""
	if not is_openai_chat_configured():
		return None, ""
	try:
		result = ask_openai(
			question,
			session=session,
			knowledge_context=knowledge_context,
			sources=sources,
			faq_rank_fn=faq_rank_fn,
			help_match_fn=help_match_fn,
		)
		return result, ""
	except frappe.ValidationError as exc:
		return None, str(exc)
	except Exception as exc:
		frappe.log_error(title="PRAI OpenAI request failed", message=frappe.get_traceback())
		return None, _openai_error_message(exc)
