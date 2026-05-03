# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""HTTP smoke tests against a running bench (Host header = site). Skips if nothing listens on :8000."""

from __future__ import annotations

import json
import os
import unittest
import urllib.error
import urllib.request

from frappe.tests.utils import FrappeTestCase

_BASE = os.environ.get("PRINTECHS_PORTAL_SMOKE_URL", "http://127.0.0.1:8000")
_HOST = os.environ.get("PRINTECHS_PORTAL_SMOKE_HOST", "demo")


def _req(
	method: str,
	path: str,
	*,
	body: bytes | None = None,
	headers: dict | None = None,
):
	h = {"Host": _HOST, "Accept": "application/json"}
	if headers:
		h.update(headers)
	return urllib.request.Request(f"{_BASE}{path}", data=body, headers=h, method=method)


def _bench_reachable() -> bool:
	try:
		with urllib.request.urlopen(_req("GET", "/api/method/ping"), timeout=3) as r:
			return r.status == 200
	except (urllib.error.URLError, TimeoutError, OSError):
		return False


@unittest.skipUnless(_bench_reachable(), f"Bench HTTP not reachable at {_BASE} (start bench or set PRINTECHS_PORTAL_SMOKE_URL)")
class TestPortalHttpSmoke(FrappeTestCase):
	def test_support_portal_page_loads(self):
		with urllib.request.urlopen(_req("GET", "/support-portal"), timeout=15) as r:
			self.assertEqual(r.status, 200)
			html = r.read().decode("utf-8", errors="replace")
		self.assertIn("Support Portal", html)
		low = html.lower()
		self.assertTrue("root" in low or "support" in low)

	def test_support_portal_deep_link_serves_spa_shell(self):
		"""Client-side routes must not 404 on refresh (website_route_rules → support-portal.html)."""
		with urllib.request.urlopen(
			_req("GET", "/support-portal/tickets/SUP-TKT-2026-00001"),
			timeout=15,
		) as r:
			self.assertEqual(r.status, 200)
			html = r.read().decode("utf-8", errors="replace")
		self.assertIn("Support Portal", html)

	def test_guest_bootstrap_json(self):
		req = _req(
			"POST",
			"/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_bootstrap",
			body=b"{}",
			headers={"Content-Type": "application/json"},
		)
		with urllib.request.urlopen(req, timeout=15) as r:
			self.assertEqual(r.status, 200)
			payload = json.loads(r.read().decode())
		self.assertIn("message", payload)
		self.assertEqual(payload["message"].get("logged_in"), False)

	def test_guest_csrf_token_json(self):
		req = _req(
			"GET",
			"/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_csrf_token",
		)
		with urllib.request.urlopen(req, timeout=15) as r:
			self.assertEqual(r.status, 200)
			payload = json.loads(r.read().decode())
		self.assertIn("message", payload)
		self.assertTrue(isinstance(payload["message"], str) and len(payload["message"]) > 8)
