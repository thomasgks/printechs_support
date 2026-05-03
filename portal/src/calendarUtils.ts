/** Pastel block in time-grid (matches dashboard accent chips). */
export type CalendarEventColor = "purple" | "blue" | "green" | "orange" | "rose" | "slate";

/** One item shown on a day cell (visit / task / reminder). */
export type CalendarEventItem = {
	date: string;
	title: string;
	/** Parent ticket name — used when ``href`` is not set (legacy link target). */
	ticket?: string;
	/** If set, navigate here (e.g. task detail). Overrides ``ticket`` for links. */
	href?: string;
	id?: string;
	/** "HH:MM" 24h — when set, event appears in the timed grid; otherwise all-day row. */
	start?: string;
	end?: string;
	color?: CalendarEventColor;
};

/** Minutes from midnight, or null if invalid. */
export function parseTimeToMinutes(t?: string): number | null {
	if (!t || !/^\d{1,2}:\d{2}$/.test(t.trim())) {
		return null;
	}
	const [h, m] = t.trim().split(":").map((x) => parseInt(x, 10));
	if (h < 0 || h > 23 || m < 0 || m > 59) {
		return null;
	}
	return h * 60 + m;
}

export const CAL_TIME_START_H = 6;
export const CAL_TIME_END_H = 19;
/** CSS px per hour in time grid */
export const CAL_PX_PER_HOUR = 52;

/** Monday-first row of cells: `null` = empty, `number` = day of month. */
export function buildMonthCells(year: number, month0: number): (number | null)[] {
	const first = new Date(year, month0, 1);
	const pad = (first.getDay() + 6) % 7;
	const last = new Date(year, month0 + 1, 0).getDate();
	const cells: (number | null)[] = [];
	for (let i = 0; i < pad; i++) {
		cells.push(null);
	}
	for (let d = 1; d <= last; d++) {
		cells.push(d);
	}
	while (cells.length % 7 !== 0) {
		cells.push(null);
	}
	return cells;
}

export function toYmd(year: number, month0: number, day: number): string {
	return `${year}-${String(month0 + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function eventsOnDay(
	items: CalendarEventItem[],
	year: number,
	month0: number,
	day: number,
): CalendarEventItem[] {
	const key = toYmd(year, month0, day);
	return items.filter((e) => e.date === key);
}

export type CalendarViewMode = "day" | "week" | "month";

/** Local calendar date (no time-of-day drift). */
export function todayCalendarDate(): Date {
	const n = new Date();
	return new Date(n.getFullYear(), n.getMonth(), n.getDate());
}

export function dateToYmd(d: Date): string {
	return toYmd(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Monday 00:00 local for the week containing `d`. */
export function startOfWeekMonday(d: Date): Date {
	const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
	const dow = (x.getDay() + 6) % 7;
	x.setDate(x.getDate() - dow);
	return x;
}

export function addDays(d: Date, n: number): Date {
	const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
	x.setDate(x.getDate() + n);
	return x;
}

/** First day of month offset by `n` months. */
export function addMonthsFirstDay(d: Date, n: number): Date {
	return new Date(d.getFullYear(), d.getMonth() + n, 1);
}
