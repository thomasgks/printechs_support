# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import os
from pathlib import Path

from printechs_support.prai_studio.zip_extraction_service import file_extension, is_scannable_file


def scan_extracted_tree(extract_dir: str) -> list[dict]:
	"""Return scannable file rows for PRAI Source Scan File child table."""
	root = Path(extract_dir)
	if not root.is_dir():
		return []

	rows: list[dict] = []
	for path in sorted(root.rglob("*")):
		if not path.is_file():
			continue
		relative = path.relative_to(root).as_posix()
		if not is_scannable_file(relative):
			continue
		try:
			size = path.stat().st_size
		except OSError:
			size = 0
		rows.append(
			{
				"file_path": relative,
				"file_name": path.name,
				"extension": file_extension(relative) or Path(relative).suffix.lower(),
				"file_size": size,
				"scan_category": _guess_category(relative),
			}
		)
	return rows


def _guess_category(relative_path: str) -> str:
	lower = relative_path.lower()
	if "promotion" in lower:
		return "Promotion"
	if lower.endswith(".sql"):
		return "Database"
	if "/api/" in lower or "controller" in lower:
		return "Api"
	if lower.endswith(".md") or lower.endswith(".txt"):
		return "Documentation"
	return "Source"
