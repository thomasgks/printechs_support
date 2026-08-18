# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import os
import zipfile
from pathlib import Path, PurePosixPath

import frappe
from frappe import _

MAX_ZIP_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_ZIP_MB = MAX_ZIP_BYTES // (1024 * 1024)

IGNORED_DIR_NAMES = frozenset(
	{
		".git",
		".svn",
		".hg",
		"bin",
		"obj",
		"node_modules",
		"packages",
		".vs",
		".idea",
		"__pycache__",
		".cursor",
	}
)

ALLOWED_SCAN_EXTENSIONS = frozenset(
	{
		".cs",
		".designer.cs",
		".resx",
		".sql",
		".json",
		".config",
		".xml",
		".md",
		".txt",
	}
)


def _resolve_uploaded_zip_path(file_url: str) -> str:
	if not file_url:
		frappe.throw(_("ZIP file is required."), frappe.ValidationError)
	if file_url.startswith("/private/files/"):
		return frappe.get_site_path("private", "files", file_url.split("/private/files/", 1)[1])
	if file_url.startswith("/files/"):
		return frappe.get_site_path("public", "files", file_url.split("/files/", 1)[1])
	frappe.throw(_("Invalid file path for ZIP upload."), frappe.ValidationError)


def _is_safe_zip_member(name: str) -> bool:
	clean = PurePosixPath(name.replace("\\", "/"))
	if clean.is_absolute():
		return False
	for part in clean.parts:
		if part in ("..", "") or part.startswith(".."):
			return False
	return True


def _should_ignore_path(relative_path: str) -> bool:
	parts = PurePosixPath(relative_path.replace("\\", "/")).parts
	return any(part.lower() in IGNORED_DIR_NAMES for part in parts)


def studio_extract_root(project_name: str) -> Path:
	root = Path(frappe.get_site_path("private", "prai_studio", project_name))
	root.mkdir(parents=True, exist_ok=True)
	return root


def extract_source_zip(*, file_url: str, project_name: str) -> tuple[str, list[str]]:
	"""Extract ZIP to private/prai_studio/{project_name}/source. Returns (extract_dir, log lines)."""
	zip_path = _resolve_uploaded_zip_path(file_url)
	if not zip_path.lower().endswith(".zip"):
		frappe.throw(_("Only .zip files are allowed."), frappe.ValidationError)
	if not os.path.isfile(zip_path):
		frappe.throw(_("Uploaded ZIP file was not found on disk."), frappe.ValidationError)

	size = os.path.getsize(zip_path)
	if size > MAX_ZIP_BYTES:
		frappe.throw(_("ZIP file exceeds the maximum allowed size ({0} MB).").format(MAX_ZIP_MB), frappe.ValidationError)

	extract_dir = studio_extract_root(project_name) / "source"
	if extract_dir.exists():
		for child in sorted(extract_dir.rglob("*"), reverse=True):
			if child.is_file():
				child.unlink(missing_ok=True)
			elif child.is_dir():
				child.rmdir()
	else:
		extract_dir.mkdir(parents=True, exist_ok=True)

	log: list[str] = []
	extracted_count = 0
	skipped_count = 0

	with zipfile.ZipFile(zip_path, "r") as zf:
		for info in zf.infolist():
			if info.is_dir():
				continue
			if not _is_safe_zip_member(info.filename):
				skipped_count += 1
				log.append(f"Skipped unsafe path: {info.filename}")
				continue
			relative = info.filename.replace("\\", "/").lstrip("/")
			if _should_ignore_path(relative):
				skipped_count += 1
				continue
			target = extract_dir / relative
			target.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(info, "r") as src, open(target, "wb") as dest:
				dest.write(src.read())
			extracted_count += 1

	log.insert(0, f"Extracted {extracted_count} file(s); skipped {skipped_count} path(s).")
	return str(extract_dir), log


def file_extension(name: str) -> str:
	lower = (name or "").lower()
	for ext in (".designer.cs",):
		if lower.endswith(ext):
			return ext
	base = Path(lower).suffix
	return base


def is_scannable_file(relative_path: str) -> bool:
	if _should_ignore_path(relative_path):
		return False
	ext = file_extension(relative_path)
	if ext == ".cs" and relative_path.lower().endswith(".designer.cs"):
		return True
	return ext in ALLOWED_SCAN_EXTENSIONS
