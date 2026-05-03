# Copyright (c) 2026, Printechs and contributors
# For license information, please see license.txt

"""Add SLA deadlines using Mon–Fri working windows and optional Holiday List."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import frappe
from frappe.utils import get_datetime, get_time, getdate


def get_holiday_dates(holiday_list_name: str | None) -> set[date]:
	if not holiday_list_name:
		return set()
	dates = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list_name},
		pluck="holiday_date",
	)
	return {getdate(d) for d in dates if d}


def parse_time_value(val) -> time | None:
	if val is None:
		return None
	if isinstance(val, time):
		return val
	if isinstance(val, timedelta):
		return (datetime.min + val).time()
	return get_time(str(val))


def _combine(d: date, t: time) -> datetime:
	return datetime.combine(d, t)


def _next_calendar_day(d: date) -> date:
	return d + timedelta(days=1)


def is_weekend(d: date) -> bool:
	return d.weekday() >= 5


def add_working_hours(
	start: datetime,
	hours: float,
	work_start: time,
	work_end: time,
	holiday_dates: set[date],
) -> datetime:
	"""Add `hours` of *working* time starting from `start` (local naive datetime)."""
	if hours <= 0:
		return get_datetime(start)

	remaining = float(hours) * 3600.0
	cur = get_datetime(start)
	max_iter = 10000
	for _ in range(max_iter):
		if remaining <= 0.0001:
			break

		d = cur.date()
		if is_weekend(d) or d in holiday_dates:
			cur = _combine(_next_calendar_day(d), work_start)
			continue

		day_start = _combine(d, work_start)
		day_end = _combine(d, work_end)

		if cur < day_start:
			cur = day_start
			continue
		if cur >= day_end:
			cur = _combine(_next_calendar_day(d), work_start)
			continue

		available = (day_end - cur).total_seconds()
		take = min(remaining, available)
		remaining -= take
		cur = cur + timedelta(seconds=take)

	return cur
