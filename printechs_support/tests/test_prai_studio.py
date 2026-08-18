# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

import io
import os
import zipfile
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from printechs_support.prai_studio.permissions import ensure_prai_studio_permissions, user_can_upload_source
from printechs_support.prai_studio.source_scanner_service import scan_extracted_tree
from printechs_support.prai_studio.zip_extraction_service import (
	_is_safe_zip_member,
	extract_source_zip,
	is_scannable_file,
	studio_extract_root,
)


class TestPraiStudio(FrappeTestCase):
	def test_safe_zip_member_blocks_traversal(self):
		self.assertFalse(_is_safe_zip_member("../etc/passwd"))
		self.assertFalse(_is_safe_zip_member("/absolute/path.cs"))
		self.assertTrue(_is_safe_zip_member("src/PromotionService.cs"))

	def test_is_scannable_file_filters(self):
		self.assertTrue(is_scannable_file("Forms/PromotionForm.cs"))
		self.assertTrue(is_scannable_file("Forms/PromotionForm.Designer.cs"))
		self.assertFalse(is_scannable_file("bin/Debug/app.dll"))
		self.assertFalse(is_scannable_file("node_modules/pkg/index.js"))

	def test_scan_extracted_tree_lists_scannable_files(self):
		root = studio_extract_root("test-scan-tree")
		source = root / "source"
		if source.exists():
			for child in sorted(source.rglob("*"), reverse=True):
				if child.is_file():
					child.unlink(missing_ok=True)
				elif child.is_dir():
					child.rmdir()
		source.mkdir(parents=True, exist_ok=True)
		(source / "Promotion.cs").write_text("class Promotion {}", encoding="utf-8")
		(source / "readme.md").write_text("# docs", encoding="utf-8")
		(source / "bin").mkdir()
		(source / "bin" / "app.dll").write_bytes(b"\x00")

		rows = scan_extracted_tree(str(source))
		paths = {row["file_path"] for row in rows}
		self.assertIn("Promotion.cs", paths)
		self.assertIn("readme.md", paths)
		self.assertNotIn("bin/app.dll", paths)

	def test_extract_source_zip_skips_unsafe_paths(self):
		project_name = "test-zip-extract"
		files_dir = Path(frappe.get_site_path("private", "files"))
		files_dir.mkdir(parents=True, exist_ok=True)
		zip_name = "prai_studio_test.zip"
		zip_path = files_dir / zip_name

		buffer = io.BytesIO()
		with zipfile.ZipFile(buffer, "w") as zf:
			zf.writestr("src/Promotion.cs", "class Promotion {}")
			zf.writestr("../escape.txt", "bad")
			zf.writestr("bin/app.dll", b"\x00")
		zip_path.write_bytes(buffer.getvalue())

		extract_dir, log = extract_source_zip(
			file_url=f"/private/files/{zip_name}",
			project_name=project_name,
		)
		extract_root = Path(extract_dir)
		self.assertTrue((extract_root / "src" / "Promotion.cs").is_file())
		self.assertFalse((extract_root / "escape.txt").exists())
		self.assertFalse((extract_root / "bin" / "app.dll").exists())
		self.assertTrue(any("unsafe path" in line.lower() for line in log))

		zip_path.unlink(missing_ok=True)
		for child in sorted(extract_root.rglob("*"), reverse=True):
			if child.is_file():
				child.unlink(missing_ok=True)
			elif child.is_dir():
				child.rmdir()

	def test_ensure_prai_studio_permissions_creates_roles(self):
		ensure_prai_studio_permissions()
		self.assertTrue(frappe.db.exists("Role", "PRAI Studio Developer"))
		self.assertTrue(frappe.db.exists("Role", "PRAI Studio Manager"))

	def test_user_can_upload_source_for_system_manager(self):
		original_user = frappe.session.user
		try:
			frappe.set_user("Administrator")
			self.assertTrue(user_can_upload_source())
		finally:
			frappe.set_user(original_user)
