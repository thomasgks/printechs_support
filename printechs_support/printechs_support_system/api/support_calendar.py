# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Calendar / Gantt: include dependency + status fields for Support Task."""

import json

import frappe
from frappe.desk import calendar as desk_calendar


@frappe.whitelist()
def get_support_task_events(doctype, start, end, field_map, filters=None, fields=None):
	field_map_d = frappe._dict(json.loads(field_map))
	fields_list = frappe.parse_json(fields) or []
	for extra in ("depends_on_tasks", "status"):
		if extra not in fields_list:
			fields_list.append(extra)
	return desk_calendar.get_events(
		doctype,
		start,
		end,
		field_map,
		filters=filters,
		fields=json.dumps(fields_list),
	)
