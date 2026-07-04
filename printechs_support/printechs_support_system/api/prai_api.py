# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json
import re
from html import unescape

import frappe
from frappe import _
from frappe.utils import cint, strip_html

from printechs_support.api.help_article import get_contextual_help
from printechs_support.permissions import get_allowed_customers, user_can_access_support_portal, user_sees_all_support_records
from printechs_support.printechs_support_system.doctype.printechs_support_settings.printechs_support_settings import (
	is_prai_mvp_enabled,
)


def _require_prai_access():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not user_can_access_support_portal(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not is_prai_mvp_enabled():
		frappe.throw(_("PRAI assistant is not enabled on this site."), frappe.ValidationError)


def _session_customer(user: str) -> str:
	customers = get_allowed_customers(user)
	if len(customers) == 1:
		return customers[0]
	return ""


def _assert_session_access(session_name: str):
	doc = frappe.get_doc("PRAI Chat Session", session_name)
	user = frappe.session.user
	if doc.user != user and not user_sees_all_support_records(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


def _truncate_title(text: str, length: int = 80) -> str:
	text = re.sub(r"\s+", " ", (text or "").strip())
	if len(text) <= length:
		return text
	return text[: length - 1].rstrip() + "…"


_STOPWORDS = frozenset(
	{
		"how",
		"what",
		"when",
		"where",
		"why",
		"who",
		"which",
		"can",
		"could",
		"would",
		"should",
		"do",
		"does",
		"did",
		"is",
		"are",
		"was",
		"were",
		"be",
		"been",
		"being",
		"the",
		"a",
		"an",
		"and",
		"or",
		"but",
		"if",
		"then",
		"in",
		"on",
		"at",
		"to",
		"for",
		"of",
		"with",
		"from",
		"by",
		"as",
		"it",
		"this",
		"that",
		"these",
		"those",
		"my",
		"your",
		"our",
		"their",
		"i",
		"we",
		"you",
		"me",
		"us",
		"please",
		"help",
		"about",
		"into",
		"up",
		"not",
		"get",
		"use",
	}
)

_GENERIC_TERMS = frozenset(
	{
		"erpnext",
		"modern",
		"pos",
		"support",
		"ticket",
		"help",
		"printechs",
		"setup",
		"set",
		"user",
		"store",
		"system",
		"create",
		"configure",
		"configuration",
	}
)

_TERM_GROUPS: tuple[frozenset[str], ...] = (
	frozenset({"setup", "configure", "configuration", "create"}),
	frozenset({"cashier", "teller"}),
	frozenset({"manager", "supervisor"}),
	frozenset({"return", "refund"}),
	frozenset({"barcode", "scanner", "scan", "scanning"}),
	frozenset({"loyalty", "points", "rewards", "reward"}),
	frozenset({"wallet", "ewallet"}),
	frozenset({"offline", "internet", "connectivity", "network"}),
	frozenset({"sync", "synchronize", "refresh", "upload"}),
	frozenset({"promotion", "discount", "offer", "campaign"}),
	frozenset({"shift", "opening", "closing", "float"}),
	frozenset({"employee", "staff"}),
	frozenset({"printer", "receipt", "print", "printing", "thermal"}),
	frozenset({"stock", "inventory", "quantity", "warehouse"}),
	frozenset({"ticket", "case", "request"}),
	frozenset({"reply", "respond", "comment", "communication"}),
	frozenset({"attachment", "upload", "file", "screenshot", "document"}),
	frozenset({"login", "signin", "password", "authentication"}),
	frozenset({"customer", "lookup", "search"}),
	frozenset({"payment", "payments", "mop", "tender", "cash", "card", "wallet", "checkout"}),
	frozenset({"report", "sales", "analytics", "register"}),
	frozenset({"item", "product", "sku"}),
	frozenset({"profile", "posprofile"}),
)


def _tokenize(text: str) -> list[str]:
	return [part for part in re.split(r"[^\w]+", (text or "").lower()) if len(part) >= 2]


def _meaningful_terms(text: str) -> list[str]:
	terms = _tokenize(text)
	out = [term for term in terms if term not in _STOPWORDS and len(term) >= 3]
	return out or terms[:3]


def _distinctive_terms(terms: list[str]) -> list[str]:
	return [term for term in terms if term not in _GENERIC_TERMS]


def _compact(text: str) -> str:
	return re.sub(r"[\W_]+", "", (text or "").lower())


def _term_in_haystack(term: str, hay: str, hay_compact: str) -> bool:
	if term in hay:
		return True
	compact_term = _compact(term)
	return bool(compact_term) and compact_term in hay_compact


def _term_variants(term: str) -> set[str]:
	for group in _TERM_GROUPS:
		if term in group:
			return set(group)
	return {term}


def _term_matches(term: str, hay: str, hay_compact: str) -> bool:
	return any(_term_in_haystack(variant, hay, hay_compact) for variant in _term_variants(term))


def _score_text(haystack: str, terms: list[str]) -> int:
	score = 0
	hay = (haystack or "").lower()
	hay_compact = _compact(haystack)
	for term in terms:
		if _term_matches(term, hay, hay_compact):
			score += 15
			if hay.startswith(term):
				score += 5
	return score


def _score_faq(row, terms: list[str]) -> int:
	meaningful = [term for term in terms if term not in _STOPWORDS] or terms
	haystack = " ".join(
		str(x or "")
		for x in (row.title, row.question, row.keywords, strip_html(row.answer or ""), row.category, row.module_area)
	)
	hay = haystack.lower()
	hay_compact = _compact(haystack)
	matched = [term for term in meaningful if _term_matches(term, hay, hay_compact)]
	if not matched:
		return 0
	distinctive = _distinctive_terms(meaningful)
	if not distinctive:
		# e.g. "What is ERPNext?" — only generic product terms; do not guess.
		return 0
	if distinctive:
		missing = [term for term in distinctive if not _term_matches(term, hay, hay_compact)]
		if missing:
			return 0
	if _has_promotion_topic(" ".join(meaningful)) and not _faq_row_has_promotion_topic(row):
		return 0
	if _has_payment_topic(" ".join(meaningful)) and not _faq_row_has_payment_topic(row):
		return 0
	if len(meaningful) >= 2 and len(matched) < 2:
		return 0
	if len(meaningful) >= 3 and (len(matched) / len(meaningful)) < 0.34:
		return 0

	score = _score_text(haystack, matched)
	title_question = f"{row.title or ''} {row.question or ''}".lower()
	title_compact = _compact(title_question)
	for term in matched:
		title_keywords = f"{row.title or ''} {row.keywords or ''}".lower()
		if _term_matches(term, title_keywords, _compact(title_keywords)):
			score += 10
		if _term_matches(term, title_question, title_compact):
			score += 15
	return score


_ITEM_INTENT_TERMS = frozenset(
	{"item", "items", "product", "products", "sku", "barcode", "stock", "inventory", "custom_is_pos"}
)
_ITEM_ACTION_TERMS = frozenset({"push", "upload"})
_PROMOTION_INTENT_TERMS = frozenset(
	{"promotion", "promotions", "discount", "discounts", "offer", "offers", "campaign", "campaigns", "deal", "deals"}
)
_PAYMENT_STRONG_TERMS = frozenset(
	{"payment", "payments", "mop", "tender", "cash", "card", "wallet", "checkout"}
)
_PAYMENT_INTENT_TERMS = _PAYMENT_STRONG_TERMS | frozenset({"mode", "modes", "type", "types"})
_BLOCK_ITEM_INTENT_TERMS = frozenset(
	{
		"payment",
		"payments",
		"mode",
		"modes",
		"type",
		"types",
		"mop",
		"tender",
		"cash",
		"card",
		"customer",
		"user",
		"cashier",
		"promotion",
		"loyalty",
		"shift",
		"printer",
		"scanner",
		"barcode",
		"return",
		"refund",
	}
)

def _has_promotion_topic(message: str) -> bool:
	terms = set(_tokenize(message))
	return bool(_PROMOTION_INTENT_TERMS & terms)


def _has_payment_topic(message: str) -> bool:
	terms = set(_tokenize(message))
	compact = _compact(message)
	if _PROMOTION_INTENT_TERMS & terms:
		return False
	if "paymenttype" in compact or "modeofpayment" in compact:
		return True
	if _PAYMENT_STRONG_TERMS & terms:
		return True
	if "payment" in terms and ({"type", "types", "mode", "modes"} & terms):
		return True
	return False


def _faq_row_has_promotion_topic(row) -> bool:
	hay = " ".join(str(x or "") for x in (row.title, row.question, row.keywords, row.category, row.module_area)).lower()
	return any(term in hay for term in _PROMOTION_INTENT_TERMS)


def _faq_row_has_payment_topic(row) -> bool:
	hay = " ".join(str(x or "") for x in (row.title, row.question, row.keywords, row.category, row.module_area)).lower()
	compact = _compact(hay)
	if "paymenttype" in compact or "modeofpayment" in compact:
		return True
	return bool(_PAYMENT_STRONG_TERMS & set(_tokenize(hay)) or "payment type" in hay or "payment mode" in hay)


_PROMOTION_LIST_TERMS = frozenset(
	{
		"list",
		"lists",
		"available",
		"show",
		"view",
		"see",
		"display",
		"which",
		"active",
		"all",
		"have",
	}
)

_FAQ_INTENT_ROUTES: tuple[tuple[str, callable], ...] = (
	("How to view list of promotions in Modern POS", lambda message: _is_promotion_list_query(message)),
	("Promotion not applying at checkout", lambda message: _is_promotion_issue_query(message)),
	("How do I set up a promotion in Modern POS?", lambda message: _is_promotion_setup_query(message)),
	("How to add a payment type in Modern POS", lambda message: _is_payment_type_modern_pos_query(message)),
	("How to push a new item to Modern POS", lambda message: _is_push_item_to_modern_pos_query(message)),
	("How to set up Modern POS step by step", lambda message: _is_modern_pos_setup_query(message)),
)


def _is_promotion_list_query(message: str) -> bool:
	terms = set(_tokenize(message))
	if not (_PROMOTION_INTENT_TERMS & terms):
		return False
	if _is_promotion_issue_query(message):
		return False
	compact = _compact(message)
	if "listof" in compact or "availablepromotion" in compact or "promotionlist" in compact:
		return True
	if _PROMOTION_LIST_TERMS & terms:
		return True
	return bool("what" in terms and ({"available", "active", "list", "have", "show"} & terms))


def _is_promotion_guide_query(message: str) -> bool:
	terms = set(_tokenize(message))
	if not (_PROMOTION_INTENT_TERMS & terms):
		return False
	if _is_promotion_issue_query(message) or _is_promotion_list_query(message):
		return False
	guide_terms = {
		"guide",
		"configure",
		"configuration",
		"types",
		"type",
		"create",
		"setup",
		"set",
		"step",
		"complete",
		"help",
		"explain",
		"benefit",
		"benefits",
		"condition",
		"conditions",
		"scope",
		"stacking",
		"rules",
	}
	return bool(guide_terms & terms or ("how" in terms and (_PROMOTION_INTENT_TERMS & terms)))


def _is_promotion_issue_query(message: str) -> bool:
	terms = set(_tokenize(message))
	if not (_PROMOTION_INTENT_TERMS & terms):
		return False
	return bool(
		{"not", "missing", "apply", "applying", "issue", "problem", "wrong", "fail", "failing", "checkout", "work", "working"}
		& terms
	)


def _is_promotion_setup_query(message: str) -> bool:
	terms = set(_tokenize(message))
	if not (_PROMOTION_INTENT_TERMS & terms):
		return False
	if _is_promotion_issue_query(message) or _is_promotion_list_query(message) or _is_promotion_guide_query(message):
		return False
	has_modern_pos = "modernpos" in _compact(message) or ("modern" in terms and "pos" in terms)
	has_action = bool({"setup", "configure", "configuration", "create", "add", "new", "set"} & terms)
	return bool(has_action or ("how" in terms and has_modern_pos))


def _is_payment_type_modern_pos_query(message: str) -> bool:
	terms = set(_tokenize(message))
	compact = _compact(message)
	if _PROMOTION_INTENT_TERMS & terms:
		return False
	has_modern_pos = "modernpos" in compact or ("modern" in terms and "pos" in terms)
	if not has_modern_pos or not _has_payment_topic(message):
		return False
	has_add_intent = bool({"add", "create", "new", "setup", "configure"} & terms)
	return bool(
		has_add_intent
		or "paymenttype" in compact
		or "modeofpayment" in compact
		or ("payment" in terms and ({"type", "types", "mode", "modes"} & terms))
	)


def _is_push_item_to_modern_pos_query(message: str) -> bool:
	terms = set(_tokenize(message))
	compact = _compact(message)
	if _BLOCK_ITEM_INTENT_TERMS & terms:
		return False
	has_modern_pos = "modernpos" in compact or ("modern" in terms and "pos" in terms)
	has_item_word = bool(_ITEM_INTENT_TERMS & terms)
	has_item_phrase = any(
		phrase in compact
		for phrase in ("newitem", "additem", "pushitem", "uploaditem", "syncitem", "positem")
	)
	has_item_action = bool(_ITEM_ACTION_TERMS & terms) and has_item_word
	has_add_new_item = bool({"add", "new"} & terms) and has_item_word
	return bool(has_modern_pos and (has_item_phrase or has_item_action or has_add_new_item or ("push" in terms and has_item_word)))


def _is_modern_pos_setup_query(message: str) -> bool:
	terms = set(_tokenize(message))
	compact = _compact(message)
	if _ITEM_INTENT_TERMS & terms and not ({"setup", "install", "configure", "configuration"} & terms):
		return False
	if _has_payment_topic(message):
		return False
	if _PROMOTION_INTENT_TERMS & terms:
		return False
	if {"loyalty", "barcode", "scanner"} & terms:
		return False
	has_modern_pos = "modernpos" in compact or ("modern" in terms and "pos" in terms)
	setup_words = {"setup", "configure", "configuration", "install", "deploy", "implementation"}
	has_setup = any(word in terms for word in setup_words) or "setup" in compact
	has_procedure = bool({"step", "procedure", "guide", "walkthrough", "terminal"} & terms)
	return bool(has_modern_pos and (has_setup or has_procedure))


def _faq_row_by_title(title: str):
	return frappe.db.get_value(
		"PRAI FAQ",
		{"title": title, "is_active": 1},
		["name", "title", "question", "answer", "keywords", "category", "module_area", "sort_order"],
		as_dict=True,
	)


_FAQ_MIN_SCORE = 45
_FAQ_AMBIGUITY_GAP = 12
_HELP_MIN_SCORE = 24


def _faq_title_overlap(message: str, row) -> int:
	distinctive = _distinctive_terms(_meaningful_terms(message))
	if not distinctive:
		return 0
	title_question = f"{row.title or ''} {row.question or ''}".lower()
	title_compact = _compact(title_question)
	return sum(1 for term in distinctive if _term_matches(term, title_question, title_compact))


def _faq_match_is_confident(message: str, scored: list) -> bool:
	if not scored:
		return False
	top_score, top_row = scored[0]
	if top_score >= 999:
		return True
	if top_score < _FAQ_MIN_SCORE:
		return False

	distinctive = _distinctive_terms(_meaningful_terms(message))
	if not distinctive:
		return False
	required = max(1, (len(distinctive) + 1) // 2)
	top_overlap = _faq_title_overlap(message, top_row)
	if top_overlap < required:
		return False

	if len(scored) >= 2 and top_score - scored[1][0] < _FAQ_AMBIGUITY_GAP:
		second_overlap = _faq_title_overlap(message, scored[1][1])
		if top_overlap > second_overlap:
			return True
		if top_overlap >= required and second_overlap >= required:
			return True
		return False

	return True


def _help_match_is_confident(matches: list) -> bool:
	if not matches:
		return False
	top_score = cint(matches[0][0])
	if top_score < _HELP_MIN_SCORE:
		return False
	if len(matches) >= 2 and top_score - cint(matches[1][0]) < 10:
		return False
	return True


def _faq_question_term_hits(message: str, row) -> int:
	distinctive = _distinctive_terms(_meaningful_terms(message))
	question = (row.question or row.title or "").lower()
	question_compact = _compact(question)
	return sum(1 for term in distinctive if _term_matches(term, question, question_compact))


def _best_faq_match(message: str, scored: list):
	if not _faq_match_is_confident(message, scored):
		return None
	ranked = sorted(
		scored,
		key=lambda item: (
			item[0],
			_faq_question_term_hits(message, item[1]),
			_faq_title_overlap(message, item[1]),
			-cint(item[1].sort_order),
		),
		reverse=True,
	)
	return ranked[0]


def _match_faq(message: str, *, limit: int = 3):
	terms = _meaningful_terms(message)
	if not terms:
		return []

	for title, matcher in _FAQ_INTENT_ROUTES:
		if matcher(message):
			row = _faq_row_by_title(title)
			if row:
				return [(999, row)]

	rows = frappe.get_all(
		"PRAI FAQ",
		filters={"is_active": 1},
		fields=["name", "title", "question", "answer", "keywords", "category", "module_area", "sort_order"],
		order_by="sort_order asc, modified desc",
		limit_page_length=500,
	)
	scored = [(_score_faq(row, terms), row) for row in rows]
	scored = [(score, row) for score, row in scored if score >= _FAQ_MIN_SCORE]
	scored.sort(key=lambda item: (-item[0], cint(item[1].sort_order)))
	return scored[:limit]


def _score_faq_context(row, terms: list[str]) -> int:
	"""Relaxed FAQ scoring used only to build OpenAI knowledge context."""
	meaningful = [term for term in terms if term not in _STOPWORDS] or terms
	haystack = " ".join(
		str(x or "")
		for x in (row.title, row.question, row.keywords, strip_html(row.answer or ""), row.category, row.module_area)
	)
	hay = haystack.lower()
	hay_compact = _compact(haystack)
	matched = [term for term in meaningful if _term_matches(term, hay, hay_compact)]
	if not matched:
		return 0
	return len(matched) * 12 + _score_text(haystack, matched) // 2


def _match_faq_for_context(message: str, *, limit: int = 5):
	terms = _meaningful_terms(message)
	if not terms:
		return []
	rows = frappe.get_all(
		"PRAI FAQ",
		filters={"is_active": 1},
		fields=["name", "title", "question", "answer", "keywords", "category", "module_area", "sort_order"],
		order_by="sort_order asc, modified desc",
		limit_page_length=500,
	)
	scored = [(_score_faq_context(row, terms), row) for row in rows]
	scored = [(score, row) for score, row in scored if score >= 12]
	scored.sort(key=lambda item: (-item[0], cint(item[1].sort_order)))
	return scored[:limit]


def _match_help_articles(message: str, *, limit: int = 3):
	customer_view = 1 if not user_sees_all_support_records(frappe.session.user) else 0
	result = get_contextual_help(search=message, customer_view=customer_view, limit=max(limit, 5))
	articles = result.get("articles") or []
	out = []
	for article in articles:
		score = cint(article.get("score"))
		if score <= 0 and not out:
			continue
		if score <= 0 and out:
			break
		out.append((score, article))
		if len(out) >= limit:
			break
	return out[:limit]


def _inline_answer_text(fragment: str) -> str:
	text = unescape(fragment or "")
	text = re.sub(r"<\s*strong[^>]*>(.*?)</strong>", r"\1", text, flags=re.I | re.S)
	text = re.sub(r"<\s*b[^>]*>(.*?)</b>", r"\1", text, flags=re.I | re.S)
	text = re.sub(r"<\s*code[^>]*>(.*?)</code>", r"\1", text, flags=re.I | re.S)
	text = re.sub(r"<\s*em[^>]*>(.*?)</em>", r"\1", text, flags=re.I | re.S)
	text = strip_html(text)
	return re.sub(r"\s+", " ", text).strip()


def _format_answer_for_chat(html: str) -> str:
	"""Convert FAQ HTML into readable chat text with numbered steps and bullets."""
	raw = unescape((html or "").strip())
	if not raw:
		return ""

	text = raw
	text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
	text = re.sub(r"<\s*/p\s*>", "\n\n", text, flags=re.I)
	text = re.sub(r"<\s*p[^>]*>", "", text, flags=re.I)

	def _format_ol(match: re.Match) -> str:
		items = re.findall(r"<\s*li[^>]*>(.*?)</li>", match.group(1), flags=re.I | re.S)
		lines = [f"{index}. {_inline_answer_text(item)}" for index, item in enumerate(items, start=1)]
		return "\n".join(lines) + "\n\n"

	def _format_ul(match: re.Match) -> str:
		items = re.findall(r"<\s*li[^>]*>(.*?)</li>", match.group(1), flags=re.I | re.S)
		lines = [f"• {_inline_answer_text(item)}" for item in items]
		return "\n".join(lines) + "\n\n"

	text = re.sub(r"<\s*ol[^>]*>(.*?)</ol>", _format_ol, text, flags=re.I | re.S)
	text = re.sub(r"<\s*ul[^>]*>(.*?)</ul>", _format_ul, text, flags=re.I | re.S)
	text = re.sub(
		r"<\s*li[^>]*>(.*?)</li>",
		lambda m: f"• {_inline_answer_text(m.group(1))}",
		text,
		flags=re.I | re.S,
	)
	text = strip_html(text)
	text = unescape(text)
	text = re.sub(r"[ \t]+\n", "\n", text)
	text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()


def _plain_answer(html: str) -> str:
	return _format_answer_for_chat(html)


def _source_dict(*, source_type: str, name: str, title: str, summary: str = "", url: str = "") -> dict:
	return {
		"type": source_type,
		"name": name,
		"title": title,
		"summary": summary,
		"url": url,
	}


def _help_article_url(name: str) -> str:
	return f"/help-center?article={name}"


def _build_faq_reply(row) -> tuple[str, str, list[dict]]:
	answer = _plain_answer(row.answer)
	sources = [_source_dict(source_type="faq", name=row.name, title=row.title, summary=answer[:180])]
	return answer, "FAQ", sources


def _build_help_reply(matches) -> tuple[str, str, list[dict]]:
	parts: list[str] = []
	sources: list[dict] = []
	for _, article in matches:
		title = article.get("title") or article.get("name") or "Help article"
		summary = (article.get("summary") or "").strip()
		name = article.get("name") or ""
		sources.append(
			_source_dict(
				source_type="help_article",
				name=name,
				title=title,
				summary=summary,
				url=_help_article_url(name) if name else "",
			)
		)
		if summary:
			parts.append(f"{title}: {summary}")
		else:
			parts.append(title)
	if len(parts) == 1:
		content = f"I found a related help article.\n\n{parts[0]}\n\nOpen Help Center for the full guide."
	else:
		content = "I found related help articles:\n\n" + "\n\n".join(f"• {part}" for part in parts)
	return content, "Help Article", sources


def _build_fallback_reply() -> tuple[str, str, list[dict], bool]:
	content = _(
		"I don't have a verified answer for that in PRAI FAQ or Help Center. "
		"Please create a support ticket and our team will assist you."
	)
	return content, "System", [], True


def _try_build_promotion_assistant_reply(message: str):
	"""Live promotion catalog / configuration guide from ERPNext POS Promotion."""
	if not (_is_promotion_list_query(message) or _is_promotion_guide_query(message)):
		return None
	from printechs_support.printechs_support_system.prai_promotion_assistant import (
		build_promotion_assistant_reply,
	)

	include_catalog = _is_promotion_list_query(message)
	include_guide = _is_promotion_guide_query(message) or include_catalog
	result = build_promotion_assistant_reply(
		message,
		include_catalog=include_catalog,
		include_guide=include_guide,
	)
	if not result:
		return None
	content, source_type, reference, sources, suggest = result
	src = sources[0]
	return (
		content,
		source_type,
		reference,
		[
			_source_dict(
				source_type=src.get("type") or "erpnext",
				name=src.get("name") or "",
				title=src.get("title") or "",
				summary=src.get("summary") or "",
				url=src.get("url") or "",
			)
		],
		suggest,
	)


def _resolve_answer(message: str, session=None):
	promotion_reply = _try_build_promotion_assistant_reply(message)
	if promotion_reply:
		return promotion_reply

	faq_matches = _match_faq(message)
	best_faq = _best_faq_match(message, faq_matches)
	if best_faq:
		_, row = best_faq
		content, source_type, sources = _build_faq_reply(row)
		return content, source_type, row.name, sources, False

	help_matches = _match_help_articles(message)
	if help_matches and _help_match_is_confident(help_matches):
		content, source_type, sources = _build_help_reply(help_matches)
		ref = sources[0]["name"] if sources else ""
		return content, source_type, ref, sources, False

	from printechs_support.printechs_support_system.api.prai_openai import (
		ask_openai_safe,
		build_knowledge_context,
		is_openai_chat_configured,
	)

	if is_openai_chat_configured():
		knowledge_context, ctx_sources = build_knowledge_context(
			message,
			faq_rank_fn=_match_faq_for_context,
			help_match_fn=_match_help_articles,
		)
		result, error = ask_openai_safe(
			message,
			session=session,
			knowledge_context=knowledge_context,
			sources=ctx_sources,
		)
		if result:
			content, sources, suggest = result
			return content, "OpenAI", "", sources, suggest
		if error:
			frappe.log_error(title="PRAI OpenAI chat failed", message=error)

	content, source_type, sources, suggest = _build_fallback_reply()
	return content, source_type, "", sources, suggest


def _append_message(session, *, role: str, content: str, source_type: str = "", source_reference: str = "", sources=None):
	session.append(
		"messages",
		{
			"role": role,
			"content": content,
			"source_type": source_type or "",
			"source_reference": source_reference or "",
			"sources_json": json.dumps(sources or []),
		},
	)


def _serialize_message(row) -> dict:
	sources = []
	raw = (row.sources_json or "").strip()
	if raw:
		try:
			sources = json.loads(raw)
		except Exception:
			sources = []
	return {
		"name": row.name,
		"role": row.role,
		"content": row.content,
		"source_type": row.source_type or "",
		"source_reference": row.source_reference or "",
		"sources": sources,
		"created_at": row.creation,
	}


def _serialize_session(doc, *, include_messages: bool = True) -> dict:
	payload = {
		"name": doc.name,
		"title": doc.title or "",
		"status": doc.status or "Open",
		"customer": doc.customer or "",
		"support_ticket": doc.support_ticket or "",
		"modified": doc.modified,
	}
	if include_messages:
		payload["messages"] = [_serialize_message(row) for row in doc.messages or []]
	return payload


def _default_ticket_type(customer: str = "") -> str:
	from printechs_support.printechs_support_system.api.portal_api import get_portal_ticket_types

	types = get_portal_ticket_types(customer=customer or None).get("types") or []
	if types:
		return types[0]["name"]
	active = frappe.get_all("Support Ticket Type", filters={"is_active": 1}, pluck="name", limit=1)
	if active:
		return active[0]
	frappe.throw(_("No active Support Ticket Type is configured."), frappe.ValidationError)


def _chat_transcript(session) -> str:
	lines = []
	for row in session.messages or []:
		label = "You" if row.role == "User" else "PRAI"
		lines.append(f"{label}: {row.content}")
	return "\n\n".join(lines)


@frappe.whitelist()
def prai_ask(message: str | None = None, session_id: str | None = None):
	"""Answer a portal user question using PRAI FAQ and Help Center search."""
	_require_prai_access()
	text = (message or "").strip()
	if not text:
		frappe.throw(_("Message is required."), frappe.ValidationError)

	user = frappe.session.user
	session = None
	sid = (session_id or "").strip()
	if sid:
		session = _assert_session_access(sid)

	if not session:
		session = frappe.get_doc(
			{
				"doctype": "PRAI Chat Session",
				"user": user,
				"customer": _session_customer(user),
				"title": _truncate_title(text),
				"status": "Open",
			}
		)

	_append_message(session, role="User", content=text)
	content, source_type, source_reference, sources, suggest_escalation = _resolve_answer(text, session=session)
	_append_message(
		session,
		role="Assistant",
		content=content,
		source_type=source_type,
		source_reference=source_reference,
		sources=sources,
	)
	session.save(ignore_permissions=True)
	frappe.db.commit()

	assistant = _serialize_message(session.messages[-1])
	return {
		"success": True,
		"session": _serialize_session(session),
		"message": assistant,
		"suggest_escalation": suggest_escalation,
		"can_escalate": not session.support_ticket,
	}


@frappe.whitelist()
def get_prai_chat_session(session_id: str | None = None):
	_require_prai_access()
	name = (session_id or "").strip()
	if not name:
		frappe.throw(_("Session is required."), frappe.ValidationError)
	doc = _assert_session_access(name)
	return {"success": True, "session": _serialize_session(doc)}


@frappe.whitelist()
def list_prai_chat_sessions(limit: int = 20):
	_require_prai_access()
	user = frappe.session.user
	filters = {"user": user}
	if user_sees_all_support_records(user) and frappe.form_dict.get("all_users"):
		filters = {}
	rows = frappe.get_all(
		"PRAI Chat Session",
		filters=filters,
		fields=["name", "title", "status", "customer", "support_ticket", "modified"],
		order_by="modified desc",
		limit_page_length=max(min(cint(limit) or 20, 100), 1),
	)
	return {"success": True, "sessions": rows}


@frappe.whitelist()
def escalate_prai_to_ticket(
	session_id: str | None = None,
	subject: str | None = None,
	description: str | None = None,
	priority: str = "Medium",
	customer: str | None = None,
	ticket_type: str | None = None,
):
	"""Create a Support Ticket from a PRAI chat session."""
	_require_prai_access()
	name = (session_id or "").strip()
	if not name:
		frappe.throw(_("Session is required."), frappe.ValidationError)
	session = _assert_session_access(name)
	if session.support_ticket:
		return {
			"success": True,
			"ticket_id": session.support_ticket,
			"session": _serialize_session(session, include_messages=False),
			"already_linked": True,
		}

	from printechs_support.printechs_support_system.api.portal_api import create_portal_ticket

	subject = (subject or session.title or "PRAI support request").strip()
	transcript = _chat_transcript(session)
	description = (description or "").strip()
	if description:
		body = f"{description.strip()}\n\n--- PRAI chat transcript ---\n{transcript}"
	else:
		body = f"Created from PRAI assistant.\n\n--- Chat transcript ---\n{transcript}"

	cust = (customer or session.customer or "").strip() or None
	if not cust and user_sees_all_support_records(frappe.session.user):
		cust = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	tt = (ticket_type or "").strip() or _default_ticket_type(cust or "")
	created = create_portal_ticket(
		subject=subject,
		description=body,
		priority=priority or "Medium",
		customer=cust,
		ticket_type=tt,
	)
	ticket_id = created.get("name") or ""
	session.support_ticket = ticket_id
	_append_message(
		session,
		role="Assistant",
		content=_("Support ticket {0} has been created from this chat.").format(ticket_id),
		source_type="Escalation",
		source_reference=ticket_id,
		sources=[_source_dict(source_type="ticket", name=ticket_id, title=subject, url=f"/support-portal/tickets/{ticket_id}")],
	)
	session.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"success": True,
		"ticket_id": ticket_id,
		"session": _serialize_session(session),
		"already_linked": False,
	}
