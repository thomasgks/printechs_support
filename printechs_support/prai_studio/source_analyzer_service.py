# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json
import re
from pathlib import Path

import frappe
from frappe import _

MAX_FILE_BYTES = 512_000
MAX_FINDINGS = 500

_CS_CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_][\w]*)")
_CS_INTERFACE_RE = re.compile(r"\binterface\s+([A-Za-z_][\w]*)")
_CS_NAMESPACE_RE = re.compile(r"\bnamespace\s+([\w.]+)")
_CS_METHOD_RE = re.compile(r"\b(?:public|protected|internal)\s+(?:static\s+)?[\w<>,\[\]\s]+\s+([A-Za-z_][\w]*)\s*\(")
_CS_ATTRIBUTE_RE = re.compile(r"\[(\w+(?:Attribute)?)\]")
_CS_API_ROUTE_RE = re.compile(r"\[(?:HttpGet|HttpPost|HttpPut|HttpDelete|Route)\b[^\]]*\]", re.I)
_CS_INHERIT_RE = re.compile(r"\bclass\s+\w+\s*:\s*([^{\n]+)")
_CS_CONTROL_RE = re.compile(r"\b(?:Button|TextBox|ComboBox|DataGridView|Label|Panel)\s+(\w+)\s*;", re.I)
_CS_PROMOTION_RE = re.compile(r"\b(promotion|discount|bundle|tier|coupon|loyalty|wallet|sync|payment|barcode)\b", re.I)
_SQL_TABLE_RE = re.compile(r"\b(?:CREATE\s+TABLE|ALTER\s+TABLE|FROM|JOIN)\s+[`\"]?([\w]+)", re.I)
_MD_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.M)
_JSON_KEY_RE = re.compile(r'"([\w]+)"\s*:')


def analyze_scan_run(scan_run_name: str) -> list[dict]:
	"""Analyze scannable files from a PRAI Source Scan Run."""
	scan = frappe.get_doc("PRAI Source Scan Run", scan_run_name)
	if scan.status != "Extracted":
		frappe.throw(_("Scan run must be in Extracted status before analysis."), frappe.ValidationError)
	extract_dir = (scan.extracted_path or "").strip()
	if not extract_dir or not Path(extract_dir).is_dir():
		frappe.throw(_("Extracted source path is missing. Re-run Extract and Scan."), frappe.ValidationError)

	findings: list[dict] = []
	for row in scan.scan_files or []:
		if len(findings) >= MAX_FINDINGS:
			break
		file_path = (row.file_path or "").strip()
		if not file_path:
			continue
		absolute = Path(extract_dir) / file_path
		if not absolute.is_file():
			continue
		try:
			if absolute.stat().st_size > MAX_FILE_BYTES:
				findings.append(
					_build_finding(
						finding_type="Ignored",
						title=f"Large file skipped: {row.file_name}",
						file_path=file_path,
						summary="File exceeds analyzer size limit (512 KB).",
						detail="",
						category=row.scan_category or "Source",
					)
				)
				continue
			content = absolute.read_text(encoding="utf-8", errors="ignore")
		except OSError as exc:
			findings.append(
				_build_finding(
					finding_type="Error",
					title=f"Could not read {row.file_name}",
					file_path=file_path,
					summary=str(exc),
					detail="",
					category=row.scan_category or "Source",
				)
			)
			continue

		ext = (row.extension or Path(file_path).suffix.lower()).lower()
		category = row.scan_category or "Source"
		if ext in {".cs"} or file_path.lower().endswith(".designer.cs"):
			findings.extend(_analyze_cs_file(file_path, content, category))
			findings.extend(_analyze_cs_deep(file_path, content, category))
		elif ext == ".sql":
			findings.extend(_analyze_sql_file(file_path, content, category))
		elif ext in {".md", ".txt"}:
			findings.extend(_analyze_text_doc(file_path, content, category))
		elif ext == ".json":
			findings.extend(_analyze_json_file(file_path, content, category))
		elif ext == ".resx":
			findings.extend(_analyze_resx_file(file_path, content, category))
		elif ext in {".xml", ".config"}:
			findings.extend(_analyze_xml_config(file_path, content, category))
		else:
			findings.append(
				_build_finding(
					finding_type="Source",
					title=f"Scanned source file: {row.file_name}",
					file_path=file_path,
					summary=f"Extension {ext or 'unknown'} — listed for knowledge generation.",
					detail=content[:1200],
					category=category,
				)
			)
	return findings[:MAX_FINDINGS]


def build_analysis_summary(findings: list[dict]) -> str:
	lines = ["PRAI Studio source analysis summary", ""]
	grouped: dict[str, list[dict]] = {}
	for row in findings:
		grouped.setdefault(row.get("finding_type") or "Source", []).append(row)
	for finding_type, rows in sorted(grouped.items()):
		lines.append(f"## {finding_type} ({len(rows)})")
		for row in rows[:40]:
			lines.append(f"- {row.get('title')} [{row.get('file_path')}]")
			summary = (row.get("summary") or "").strip()
			if summary:
				lines.append(f"  {summary}")
		if len(rows) > 40:
			lines.append(f"  ... and {len(rows) - 40} more")
		lines.append("")
	return "\n".join(lines).strip()


def _build_finding(
	*,
	finding_type: str,
	title: str,
	file_path: str,
	summary: str,
	detail: str,
	category: str,
) -> dict:
	return {
		"finding_type": finding_type,
		"title": title[:180],
		"file_path": file_path,
		"summary": summary[:1000],
		"detail": detail[:5000],
		"scan_category": category,
	}


def _analyze_cs_file(file_path: str, content: str, category: str) -> list[dict]:
	findings: list[dict] = []
	classes = _CS_CLASS_RE.findall(content)
	methods = _CS_METHOD_RE.findall(content)
	promotion_hits = sorted(set(_CS_PROMOTION_RE.findall(content)))
	lower_path = file_path.lower()

	if "promotion" in lower_path or promotion_hits:
		type_name = "Promotion"
		category = "Promotion"
	elif lower_path.endswith(".designer.cs") or "/forms/" in lower_path.replace("\\", "/"):
		type_name = "Form"
		category = "Source"
	elif "controller" in lower_path or "api" in lower_path:
		type_name = "Api"
		category = "Api"
	else:
		type_name = "Source"

	class_list = ", ".join(sorted(set(classes))[:12])
	method_list = ", ".join(sorted(set(methods))[:16])
	summary_parts = []
	if class_list:
		summary_parts.append(f"Classes: {class_list}")
	if method_list:
		summary_parts.append(f"Methods: {method_list}")
	if promotion_hits:
		summary_parts.append(f"Promotion terms: {', '.join(promotion_hits[:8])}")

	findings.append(
		_build_finding(
			finding_type=type_name,
			title=f"C# {type_name.lower()} file: {Path(file_path).name}",
			file_path=file_path,
			summary=" | ".join(summary_parts) or "C# source file detected.",
			detail=_extract_cs_excerpt(content),
			category=category,
		)
	)

	for class_name in sorted(set(classes))[:8]:
		if not _looks_like_feature_class(class_name):
			continue
		findings.append(
			_build_finding(
				finding_type=type_name,
				title=f"Feature class: {class_name}",
				file_path=file_path,
				summary=f"Defined in {Path(file_path).name}",
				detail=_extract_class_block(content, class_name),
				category=category,
			)
		)
	return findings


def _analyze_cs_deep(file_path: str, content: str, category: str) -> list[dict]:
	"""Phase 3: richer C# structure hints for guides and health-aware generation."""
	findings: list[dict] = []
	lower_path = file_path.lower()
	namespaces = _CS_NAMESPACE_RE.findall(content)
	interfaces = _CS_INTERFACE_RE.findall(content)
	attributes = sorted(set(_CS_ATTRIBUTE_RE.findall(content)))[:12]
	routes = _CS_API_ROUTE_RE.findall(content)
	controls = _CS_CONTROL_RE.findall(content) if lower_path.endswith(".designer.cs") else []
	base_types = [part.strip() for part in _CS_INHERIT_RE.findall(content) for part in part.split(",")][:6]

	if namespaces:
		findings.append(
			_build_finding(
				finding_type="Source",
				title=f"Namespace: {namespaces[0]}",
				file_path=file_path,
				summary=f"Namespaces detected: {', '.join(namespaces[:4])}",
				detail="",
				category=category,
			)
		)
	if interfaces:
		findings.append(
			_build_finding(
				finding_type="Api",
				title=f"Interfaces in {Path(file_path).name}",
				file_path=file_path,
				summary=f"Interfaces: {', '.join(interfaces[:8])}",
				detail="",
				category="Api",
			)
		)
	if routes or "controller" in lower_path or "api" in lower_path:
		findings.append(
			_build_finding(
				finding_type="Api",
				title=f"API endpoints in {Path(file_path).name}",
				file_path=file_path,
				summary=f"Route attributes: {len(routes)} | Attributes: {', '.join(attributes[:8]) or 'none'}",
				detail="\n".join(routes[:10]),
				category="Api",
			)
		)
	if controls:
		findings.append(
			_build_finding(
				finding_type="Form",
				title=f"UI controls in {Path(file_path).name}",
				file_path=file_path,
				summary=f"Controls: {', '.join(controls[:16])}",
				detail="",
				category="Source",
			)
		)
	if base_types:
		findings.append(
			_build_finding(
				finding_type="Source",
				title=f"Inheritance chain in {Path(file_path).name}",
				file_path=file_path,
				summary=f"Base types: {', '.join(base_types)}",
				detail="",
				category=category,
			)
		)
	for token in ("syncservice", "paymentservice", "promotionservice", "barcodeservice"):
		if token in content.lower().replace("_", ""):
			label = token.replace("service", " Service").title().replace(" ", "")
			findings.append(
				_build_finding(
					finding_type="Source",
					title=f"Service pattern: {label}",
					file_path=file_path,
					summary=f"Detected {label} pattern in source.",
					detail=_extract_cs_excerpt(content, 1200),
					category=category,
				)
			)
			break
	return findings


def _analyze_sql_file(file_path: str, content: str, category: str) -> list[dict]:
	findings: list[dict] = []
	tables = sorted({match.lower() for match in _SQL_TABLE_RE.findall(content) if len(match) > 2})
	findings.append(
		_build_finding(
			finding_type="Database",
			title=f"SQL script: {Path(file_path).name}",
			file_path=file_path,
			summary=f"Tables referenced: {', '.join(tables[:20]) or 'none detected'}",
			detail=content[:3000],
			category="Database",
		)
	)
	for table in tables[:15]:
		if table in {"select", "where", "inner", "left", "right", "join", "from"}:
			continue
		findings.append(
			_build_finding(
				finding_type="Database",
				title=f"Database table: {table}",
				file_path=file_path,
				summary=f"Referenced in {Path(file_path).name}",
				detail="",
				category="Database",
			)
		)
	return findings


def _analyze_text_doc(file_path: str, content: str, category: str) -> list[dict]:
	findings: list[dict] = []
	headings = [match.strip() for match in _MD_HEADING_RE.findall(content)]
	findings.append(
		_build_finding(
			finding_type="Documentation",
			title=f"Documentation: {Path(file_path).name}",
			file_path=file_path,
			summary=f"Sections: {', '.join(headings[:12]) or 'plain text'}",
			detail=content[:4000],
			category="Documentation",
		)
	)
	for heading in headings[:12]:
		if len(heading) < 6:
			continue
		findings.append(
			_build_finding(
				finding_type="Documentation",
				title=f"Doc topic: {heading}",
				file_path=file_path,
				summary=f"From {Path(file_path).name}",
				detail=_extract_section_for_heading(content, heading),
				category="Documentation",
			)
		)
	return findings


def _analyze_json_file(file_path: str, content: str, category: str) -> list[dict]:
	keys = sorted(set(_JSON_KEY_RE.findall(content)))[:30]
	summary = f"Top-level keys: {', '.join(keys[:20])}" if keys else "JSON configuration file"
	detail = content[:3000]
	try:
		payload = json.loads(content)
		if isinstance(payload, dict):
			summary = f"JSON object with keys: {', '.join(list(payload.keys())[:20])}"
	except json.JSONDecodeError:
		pass
	return [
		_build_finding(
			finding_type="Configuration",
			title=f"JSON config: {Path(file_path).name}",
			file_path=file_path,
			summary=summary,
			detail=detail,
			category=category,
		)
	]


def _analyze_resx_file(file_path: str, content: str, category: str) -> list[dict]:
	names = re.findall(r'<data name="([^"]+)"', content)
	summary = f"Resource keys: {', '.join(names[:20])}" if names else "WinForms/WPF resource file"
	return [
		_build_finding(
			finding_type="Form",
			title=f"UI resources: {Path(file_path).name}",
			file_path=file_path,
			summary=summary,
			detail=content[:2500],
			category="Source",
		)
	]


def _analyze_xml_config(file_path: str, content: str, category: str) -> list[dict]:
	return [
		_build_finding(
			finding_type="Configuration",
			title=f"Config/XML: {Path(file_path).name}",
			file_path=file_path,
			summary="Application configuration or XML definition.",
			detail=content[:3000],
			category=category,
		)
	]


def _looks_like_feature_class(class_name: str) -> bool:
	lower = class_name.lower()
	if lower in {"program", "startup", "settings", "helper", "utils", "base", "form1"}:
		return False
	return any(token in lower for token in ("promotion", "pos", "payment", "discount", "loyalty", "wallet", "sync", "barcode", "item"))


def _extract_cs_excerpt(content: str, limit: int = 1800) -> str:
	lines = []
	for line in content.splitlines():
		strip = line.strip()
		if not strip or strip.startswith("//"):
			continue
		if _CS_PROMOTION_RE.search(strip) or strip.startswith("public ") or strip.startswith("class "):
			lines.append(strip)
		if len("\n".join(lines)) > limit:
			break
	return "\n".join(lines)[:limit]


def _extract_class_block(content: str, class_name: str, limit: int = 2500) -> str:
	match = re.search(rf"\bclass\s+{re.escape(class_name)}\b[\s\S]{{0,{limit}}}", content)
	return (match.group(0) if match else "")[:limit]


def _extract_section_for_heading(content: str, heading: str, limit: int = 2000) -> str:
	pattern = re.compile(rf"^#{{1,3}}\s+{re.escape(heading)}\s*$", re.M)
	match = pattern.search(content)
	if not match:
		return content[:limit]
	start = match.end()
	next_heading = re.search(r"^#{1,3}\s+", content[start:], re.M)
	end = start + next_heading.start() if next_heading else len(content)
	return content[start:end].strip()[:limit]
