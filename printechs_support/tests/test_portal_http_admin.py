# Copyright (c) 2026, Printechs and contributors
# License: MIT. See license.txt

"""
HTTP tests: log in as Administrator (password via PRINTECHS_TEST_ADMIN_PASSWORD, default ``admin``)
and call portal APIs the same way the React SPA does (session cookie + CSRF).

These tests hit a **live** bench (default ``http://127.0.0.1:8000``) and **create a real Support Ticket**.
They run only when ``PRINTECHS_RUN_PORTAL_HTTP_TESTS`` is set to ``1``/``true`` — not on every
``bench run-tests``, so routine CI/local runs do not pollute your site with ``[http-admin-test]`` tickets.
"""

from __future__ import annotations

import json
import os
import unittest
import urllib.error
import urllib.request

import frappe
from frappe.tests.utils import FrappeTestCase

try:
	import requests
except ImportError:
	requests = None

_BASE = os.environ.get("PRINTECHS_PORTAL_SMOKE_URL", "http://127.0.0.1:8000")
_HOST = os.environ.get("PRINTECHS_PORTAL_SMOKE_HOST", "demo")
_ADMIN_PASSWORD = os.environ.get("PRINTECHS_TEST_ADMIN_PASSWORD", "admin")


def _portal_http_ticket_tests_enabled() -> bool:
	v = (os.environ.get("PRINTECHS_RUN_PORTAL_HTTP_TESTS") or "").strip().lower()
	return v in ("1", "true", "yes", "on")


def _bench_reachable() -> bool:
	try:
		with urllib.request.urlopen(
			urllib.request.Request(
				f"{_BASE}/api/method/ping",
				headers={"Host": _HOST},
				method="GET",
			),
			timeout=3,
		) as r:
			return r.status == 200
	except (urllib.error.URLError, TimeoutError, OSError):
		return False


@unittest.skipIf(requests is None, "requests not installed")
@unittest.skipUnless(
	_portal_http_ticket_tests_enabled(),
	"Skipped by default (creates a Support Ticket on the live bench). "
	"Set PRINTECHS_RUN_PORTAL_HTTP_TESTS=1 and ensure the server is reachable.",
)
@unittest.skipUnless(_bench_reachable(), f"Bench HTTP not reachable at {_BASE}")
class TestPortalHttpAdministrator(FrappeTestCase):
	def test_login_and_portal_api_chain(self):
		s = requests.Session()
		r = s.post(
			f"{_BASE}/api/method/login",
			json={"usr": "Administrator", "pwd": _ADMIN_PASSWORD},
			headers={"Host": _HOST},
			timeout=30,
		)
		self.assertEqual(r.status_code, 200, msg=r.text[:500])
		body = r.json()
		self.assertIn(body.get("message"), ("Logged In", "No App"), msg=body)

		r_csrf = s.get(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_csrf_token",
			headers={"Host": _HOST},
			timeout=30,
		)
		self.assertEqual(r_csrf.status_code, 200, msg=r_csrf.text[:500])
		csrf = r_csrf.json()["message"]
		self.assertTrue(isinstance(csrf, str) and len(csrf) > 8)

		h = {"Host": _HOST, "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf}

		r_boot = s.post(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_bootstrap",
			json={},
			headers=h,
			timeout=30,
		)
		self.assertEqual(r_boot.status_code, 200, msg=r_boot.text[:500])
		boot = r_boot.json()["message"]
		self.assertTrue(boot.get("logged_in"))
		self.assertEqual(boot.get("user"), "Administrator")
		self.assertTrue(boot.get("internal") is True)

		r_tickets = s.post(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_tickets",
			json={"limit": 10},
			headers=h,
			timeout=30,
		)
		self.assertEqual(r_tickets.status_code, 200, msg=r_tickets.text[:500])
		ticket_rows = r_tickets.json().get("message")
		self.assertIsInstance(ticket_rows, list)

		cust_name = None
		r_cust = s.post(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_customers",
			json={},
			headers=h,
			timeout=30,
		)
		if r_cust.status_code == 200:
			cust_payload = r_cust.json().get("message") or {}
			self.assertIn("customers", cust_payload)
			customers = cust_payload["customers"]
			self.assertIsInstance(customers, list)
			if customers:
				cust_name = customers[0]["name"]
		elif ticket_rows and ticket_rows[0].get("customer"):
			# Older benches without get_portal_ticket_customers: reuse a customer from an existing ticket.
			cust_name = ticket_rows[0]["customer"]

		if not cust_name:
			# Same DB as this test run: pick any Customer so we can still exercise create_portal_ticket over HTTP.
			names = frappe.get_all("Customer", pluck="name", limit_page_length=1)
			if names:
				cust_name = names[0]

		if not cust_name:
			return

		r_types = s.post(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_types",
			json={"customer": cust_name},
			headers=h,
			timeout=30,
		)
		self.assertEqual(r_types.status_code, 200, msg=r_types.text[:500])
		types = (r_types.json().get("message") or {}).get("types") or []
		if not types:
			return
		ticket_type = types[0]["name"]
		tag = "http-admin-test"
		r_create = s.post(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.create_portal_ticket",
			json={
				"subject": f"[{tag}] Portal HTTP admin test",
				"description": "<p>Automated Administrator HTTP test.</p>",
				"priority": "Low",
				"customer": cust_name,
				"ticket_type": ticket_type,
			},
			headers=h,
			timeout=60,
		)
		self.assertEqual(r_create.status_code, 200, msg=r_create.text[:800])
		created = r_create.json().get("message") or {}
		self.assertIn("name", created)
		ticket_name = created["name"]

		r_one = s.post(
			f"{_BASE}/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_ticket",
			json={"name": ticket_name},
			headers=h,
			timeout=30,
		)
		self.assertEqual(r_one.status_code, 200, msg=r_one.text[:500])
		self.assertEqual(r_one.json()["message"].get("name"), ticket_name)
