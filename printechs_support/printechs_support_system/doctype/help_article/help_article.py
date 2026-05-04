# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import nowdate, sanitize_html


class HelpArticle(Document):
	def before_insert(self):
		if not (self.article_code or "").strip():
			year = nowdate()[:4]
			self.article_code = make_autoname(f"HELP-{year}-.####")

	def validate(self):
		self._sync_publication_status()
		self._sanitize_content()
		self._set_video_embed()
		self._validate_unique_title_category()
		self._make_customer_files_public()

	def _sync_publication_status(self):
		self.status = self.status or "Published"
		self.is_published = 1 if self.status == "Published" else 0

	def _sanitize_content(self):
		self.content = sanitize_html(self.content or "")
		if self.video_embed_html:
			self.video_embed_html = sanitize_html(self.video_embed_html)

	def _set_video_embed(self):
		url = (self.video_url or "").strip()
		if not url:
			self.video_url = ""
			self.video_embed_html = ""
			return
		parsed = urlparse(url)
		if parsed.scheme and parsed.scheme not in {"http", "https"}:
			frappe.throw(_("Only http/https video URLs are allowed."), frappe.ValidationError)
		self.video_url = url
		self.video_embed_html = _video_embed_html(url)

	def _validate_unique_title_category(self):
		if not self.title or not self.category:
			return
		existing = frappe.db.get_value(
			"Help Article",
			{"title": self.title.strip(), "category": self.category, "name": ["!=", self.name]},
			"name",
		)
		if existing:
			frappe.throw(_("An article with this Title and Category already exists."), frappe.ValidationError)

	def _make_customer_files_public(self):
		if not (self.is_published and self.show_in_portal and self.allow_customer_view):
			return
		for row in self.attachments or []:
			file_url = (row.file or "").strip()
			if not file_url.startswith("/private/files/"):
				continue
			file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
			if not file_name:
				continue
			try:
				file_doc = frappe.get_doc("File", file_name)
				if file_doc.is_private:
					public_url = f"/files/{file_url.split('/')[-1]}"
					public_path = Path(frappe.get_site_path("public", "files", file_url.split("/")[-1]))
					if public_path.exists():
						file_doc.file_url = public_url
						file_doc.is_private = 0
						file_doc.attached_to_field = None
						file_doc.db_update()
						row.file = public_url
						continue
					if file_doc.attached_to_field:
						file_doc.attached_to_field = None
					file_doc.is_private = 0
					file_doc.save(ignore_permissions=True)
					row.file = file_doc.file_url
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Help Article public attachment conversion")


def _iframe(src: str, title: str = "Help video") -> str:
	return (
		'<div class="help-video-embed">'
		f'<iframe src="{quote(src, safe=":/?&=#%.+-_")}" title="{frappe.utils.escape_html(title)}" '
		'style="width:100%;min-height:360px;border:0;border-radius:12px;" '
		'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
		'allowfullscreen loading="lazy"></iframe></div>'
	)


def _video_embed_html(url: str) -> str:
	parsed = urlparse(url)
	host = (parsed.netloc or "").lower()
	path = parsed.path or ""

	if "youtube.com" in host:
		video_id = (parse_qs(parsed.query).get("v") or [""])[0]
		if not video_id and path.startswith("/shorts/"):
			video_id = path.split("/", 2)[2].split("/")[0]
		if video_id:
			return _iframe(f"https://www.youtube.com/embed/{video_id}", "YouTube video")
	if "youtu.be" in host:
		video_id = path.strip("/").split("/")[0]
		if video_id:
			return _iframe(f"https://www.youtube.com/embed/{video_id}", "YouTube video")
	if "vimeo.com" in host:
		video_id = path.strip("/").split("/")[0]
		if video_id:
			return _iframe(f"https://player.vimeo.com/video/{video_id}", "Vimeo video")
	if "drive.google.com" in host:
		parts = [p for p in path.split("/") if p]
		file_id = ""
		if "d" in parts:
			idx = parts.index("d")
			if idx + 1 < len(parts):
				file_id = parts[idx + 1]
		if file_id:
			return _iframe(f"https://drive.google.com/file/d/{file_id}/preview", "Google Drive video")
	if path.lower().endswith((".mp4", ".webm", ".ogg", ".mov")):
		src = quote(url, safe=":/?&=#%.+-_")
		return (
			'<video controls style="width:100%;max-height:520px;border-radius:12px;" preload="metadata">'
			f'<source src="{src}"></video>'
		)
	return ""
