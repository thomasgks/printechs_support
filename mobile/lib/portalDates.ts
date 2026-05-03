/**
 * Frappe portal returns naive datetimes like `2026-04-18 00:00:00`.
 * Do not derive calendar day via `new Date(str).toISOString().slice(0, 10)` — that uses UTC
 * and can show the previous calendar day. Prefer `due_date_calendar` from the API when present.
 */

export function calendarDateFromPortalDoc(doc: Record<string, unknown>): string | null {
	const cal = doc.due_date_calendar;
	if (typeof cal === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(cal.trim())) {
		return cal.trim();
	}
	const raw = doc.due_date;
	if (raw == null || raw === '') return null;
	const s = String(raw).trim();
	const m = /^(\d{4}-\d{2}-\d{2})/.exec(s);
	return m ? m[1] : null;
}

/** For UI labels — stable wall-calendar date, not UTC. */
export function formatPortalDueCalendar(doc: Record<string, unknown>): string {
	const d = calendarDateFromPortalDoc(doc);
	return d ?? (doc.due_date != null ? String(doc.due_date) : '');
}

/** Use after save + refetch: compare user-picked YYYY-MM-DD to API doc (not `Date`/`toISOString`). */
export function portalDueCalendarMatchesExpected(expectedYmd: string, doc: Record<string, unknown>): boolean {
	const got = calendarDateFromPortalDoc(doc);
	return got != null && got === expectedYmd;
}
