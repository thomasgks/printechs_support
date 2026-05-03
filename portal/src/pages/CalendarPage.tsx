import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import CalendarTimeGrid from "../components/CalendarTimeGrid";
import {
	getPortalBootstrap,
	getPortalTasks,
	getPortalTickets,
	isPortalMockDataEnabled,
	portalTaskPath,
	portalTicketPath,
} from "../api";
import {
	addDays,
	addMonthsFirstDay,
	buildMonthCells,
	dateToYmd,
	eventsOnDay,
	type CalendarEventItem,
	type CalendarViewMode,
	startOfWeekMonday,
	todayCalendarDate,
	toYmd,
} from "../calendarUtils";
import { MOCK_CALENDAR_EVENTS } from "../portalMock";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function isToday(year: number, month0: number, day: number): boolean {
	const t = todayCalendarDate();
	return t.getFullYear() === year && t.getMonth() === month0 && t.getDate() === day;
}

function isSameCalendarDate(a: Date, y: number, month0: number, day: number): boolean {
	return a.getFullYear() === y && a.getMonth() === month0 && a.getDate() === day;
}

function eventLinkTo(ev: CalendarEventItem): string | null {
	if (ev.href?.trim()) {
		return ev.href;
	}
	if (ev.ticket?.trim()) {
		return portalTicketPath(ev.ticket);
	}
	return null;
}

function EventBlocks({ events: evs }: { events: CalendarEventItem[] }) {
	return (
		<>
			{evs.map((ev, evIdx) => {
				const to = eventLinkTo(ev);
				return (
					<div
						key={`${ev.date}-${evIdx}-${ev.id ?? ev.title}`}
						className={`calendar-event calendar-event--${ev.color ?? "purple"}`}
						title={ev.title}
					>
						{to ? (
							<Link to={to} className="calendar-event-link">
								{ev.title}
							</Link>
						) : (
							<span>{ev.title}</span>
						)}
					</div>
				);
			})}
		</>
	);
}

export default function CalendarPage() {
	const [viewMode, setViewMode] = useState<CalendarViewMode>("month");
	const [cursor, setCursor] = useState(() => {
		if (isPortalMockDataEnabled()) {
			return new Date(2026, 3, 8);
		}
		return todayCalendarDate();
	});

	const [events, setEvents] = useState<CalendarEventItem[]>([]);
	const [loading, setLoading] = useState(() => !isPortalMockDataEnabled());
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		if (isPortalMockDataEnabled()) {
			setEvents(MOCK_CALENDAR_EVENTS);
			setLoading(false);
			setErr(null);
			return;
		}
		let cancelled = false;
		(async () => {
			setLoading(true);
			setErr(null);
			try {
				const [tasks, tickets, boot] = await Promise.all([
					getPortalTasks(200),
					getPortalTickets(200),
					getPortalBootstrap(),
				]);
				if (cancelled) {
					return;
				}
				const colors = ["purple", "blue", "green", "orange", "rose", "slate"] as const;
				const me =
					boot && typeof boot === "object" && "logged_in" in boot && boot.logged_in && "user" in boot
						? String((boot as { user?: string }).user ?? "").trim()
						: "";
				const todayYmd = dateToYmd(todayCalendarDate());
				const taskTerminal = new Set(["Completed", "Cancelled"]);
				const ticketTerminal = new Set(["Resolved", "Closed", "Cancelled"]);

				function dueYmd(row: Record<string, unknown>): string | null {
					const cal = row.due_date_calendar;
					if (typeof cal === "string" && /^\d{4}-\d{2}-\d{2}$/.test(cal.trim())) {
						return cal.trim();
					}
					const d = row.due_date;
					if (typeof d === "string" && d.length >= 10 && d[4] === "-" && d[7] === "-") {
						return d.slice(0, 10);
					}
					return null;
				}

				function dueTimeHm(row: Record<string, unknown>): string | undefined {
					const d = row.due_date;
					if (typeof d !== "string" || d.length < 16) {
						return undefined;
					}
					const hm = d.slice(11, 16);
					return /^\d{2}:\d{2}$/.test(hm) ? hm : undefined;
				}

				function isTaskAssignedToMe(row: Record<string, unknown>): boolean {
					if (!me) {
						return false;
					}
					if (String(row.assigned_to_user ?? "").trim() === me) {
						return true;
					}
					const au = row.assigned_users;
					if (Array.isArray(au)) {
						return au.some((u) => String(u).trim() === me);
					}
					return false;
				}

				function isTicketAssignedToMe(row: Record<string, unknown>): boolean {
					if (!me) {
						return false;
					}
					if (String(row.assigned_to ?? "").trim() === me) {
						return true;
					}
					const au = row.assigned_users;
					if (Array.isArray(au)) {
						return au.some((u) => String(u).trim() === me);
					}
					return false;
				}

				let idx = 0;
				const mapped: CalendarEventItem[] = [];

				for (const t of tasks) {
					const row = t as Record<string, unknown>;
					const date = dueYmd(row);
					if (!date) {
						continue;
					}
					const start = dueTimeHm(row);
					mapped.push({
						date,
						title: String(row.subject ?? row.name ?? "Task"),
						ticket: String(row.support_ticket ?? ""),
						href: portalTaskPath(String(row.name ?? "")),
						id: String(row.name ?? ""),
						start,
						color: colors[idx % colors.length],
					});
					idx += 1;
				}

				for (const tk of tickets) {
					const row = tk as Record<string, unknown>;
					const date = dueYmd(row);
					if (!date) {
						continue;
					}
					const start = dueTimeHm(row);
					mapped.push({
						date,
						title: `Ticket · ${String(row.subject ?? row.name ?? "Ticket")}`,
						href: portalTicketPath(String(row.name ?? "")),
						ticket: String(row.name ?? ""),
						id: `tkt-${String(row.name ?? "")}`,
						start,
						color: colors[idx % colors.length],
					});
					idx += 1;
				}

				/* Assigned work with no due date: show on today so technicians still see it (planning). */
				for (const t of tasks) {
					const row = t as Record<string, unknown>;
					if (dueYmd(row)) {
						continue;
					}
					if (!isTaskAssignedToMe(row)) {
						continue;
					}
					if (taskTerminal.has(String(row.status ?? ""))) {
						continue;
					}
					mapped.push({
						date: todayYmd,
						title: `No due date · ${String(row.subject ?? row.name ?? "Task")}`,
						ticket: String(row.support_ticket ?? ""),
						href: portalTaskPath(String(row.name ?? "")),
						id: `unsched-task-${String(row.name ?? "")}`,
						color: "slate",
					});
					idx += 1;
				}

				for (const tk of tickets) {
					const row = tk as Record<string, unknown>;
					if (dueYmd(row)) {
						continue;
					}
					if (!isTicketAssignedToMe(row)) {
						continue;
					}
					if (ticketTerminal.has(String(row.status ?? ""))) {
						continue;
					}
					mapped.push({
						date: todayYmd,
						title: `No due date · Ticket · ${String(row.subject ?? row.name ?? "Ticket")}`,
						href: portalTicketPath(String(row.name ?? "")),
						ticket: String(row.name ?? ""),
						id: `unsched-tkt-${String(row.name ?? "")}`,
						color: "slate",
					});
					idx += 1;
				}

				setEvents(mapped);
			} catch (e) {
				if (!cancelled) {
					setErr(e instanceof Error ? e.message : "Failed to load");
					setEvents([]);
				}
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	const year = cursor.getFullYear();
	const month0 = cursor.getMonth();

	const cells = useMemo(() => buildMonthCells(year, month0), [year, month0]);

	const weekStart = useMemo(() => startOfWeekMonday(cursor), [cursor]);
	const weekDays = useMemo(() => [0, 1, 2, 3, 4, 5, 6].map((i) => addDays(weekStart, i)), [weekStart]);
	const weekEnd = weekDays[6]!;

	const periodLabel = useMemo(() => {
		if (viewMode === "day") {
			return cursor.toLocaleDateString(undefined, {
				weekday: "long",
				month: "long",
				day: "numeric",
				year: "numeric",
			});
		}
		if (viewMode === "week") {
			const a = weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" });
			const b = weekEnd.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
			return `${a} – ${b}`;
		}
		return cursor.toLocaleString(undefined, { month: "long", year: "numeric" });
	}, [viewMode, cursor, weekStart, weekEnd]);

	const countLabel = useMemo(() => {
		if (loading) {
			return "Loading…";
		}
		if (viewMode === "day") {
			const n = eventsOnDay(events, year, month0, cursor.getDate()).length;
			return `${n} item(s) this day`;
		}
		if (viewMode === "week") {
			const start = dateToYmd(weekStart);
			const end = dateToYmd(weekEnd);
			const n = events.filter((e) => e.date >= start && e.date <= end).length;
			return `${n} item(s) this week`;
		}
		const prefix = `${year}-${String(month0 + 1).padStart(2, "0")}`;
		const n = events.filter((e) => e.date.startsWith(prefix)).length;
		return `${n} item(s) this month`;
	}, [loading, viewMode, events, year, month0, cursor, weekStart, weekEnd]);

	function goPrev() {
		if (viewMode === "month") {
			setCursor((c) => addMonthsFirstDay(c, -1));
		} else if (viewMode === "week") {
			setCursor((c) => addDays(c, -7));
		} else {
			setCursor((c) => addDays(c, -1));
		}
	}

	function goNext() {
		if (viewMode === "month") {
			setCursor((c) => addMonthsFirstDay(c, 1));
		} else if (viewMode === "week") {
			setCursor((c) => addDays(c, 7));
		} else {
			setCursor((c) => addDays(c, 1));
		}
	}

	function goToday() {
		setCursor(todayCalendarDate());
	}

	const navAria =
		viewMode === "month" ? "Previous month" : viewMode === "week" ? "Previous week" : "Previous day";
	const navAriaNext =
		viewMode === "month" ? "Next month" : viewMode === "week" ? "Next week" : "Next day";

	const isTodayCol = (d: Date) =>
		isSameCalendarDate(todayCalendarDate(), d.getFullYear(), d.getMonth(), d.getDate());

	return (
		<div className="page-grid calendar-page">
			<div className="calendar-intro-bar">
				<div>
					<p className="eyebrow">Schedule</p>
					<h2 className="calendar-intro-title">Calendar</h2>
					<p className="muted small calendar-intro-desc">
						{isPortalMockDataEnabled()
							? "Mock data: timed blocks in Daily/Weekly; April 2026 has the fullest sample."
							: "Scheduled by due date on each task/ticket. Items assigned to you with no due date appear on today as “No due date …” (slate). Set Due on the ticket or task to place it on a specific day."}
					</p>
				</div>
			</div>

			<section className="calendar-shell card calendar-shell--grow" aria-label="Calendar">
				<div className="calendar-view-tabs" role="tablist" aria-label="Calendar view">
					{(["day", "week", "month"] as const).map((mode) => (
						<button
							key={mode}
							type="button"
							role="tab"
							aria-selected={viewMode === mode}
							className={`calendar-view-tab${viewMode === mode ? " calendar-view-tab--active" : ""}`}
							onClick={() => setViewMode(mode)}
						>
							{mode === "day" ? "Daily" : mode === "week" ? "Weekly" : "Monthly"}
						</button>
					))}
				</div>

				<header className="calendar-toolbar">
					<button type="button" className="calendar-nav-btn" onClick={goPrev} aria-label={navAria}>
						←
					</button>
					<div className="calendar-toolbar-center">
						<h3 className="calendar-month-title">{periodLabel}</h3>
						<p className="calendar-sub muted small">{countLabel}</p>
					</div>
					<button type="button" className="calendar-nav-btn" onClick={goNext} aria-label={navAriaNext}>
						→
					</button>
				</header>
				<div className="calendar-toolbar-row">
					<button type="button" className="btn-text" onClick={goToday}>
						Today
					</button>
				</div>

				{err ? <p className="error-text calendar-err">{err}</p> : null}

				{viewMode === "month" ? (
					<>
						<div className="calendar-weekdays" aria-hidden>
							{WEEKDAYS.map((d) => (
								<div key={d} className="calendar-weekday">
									{d}
								</div>
							))}
						</div>

						<div className="calendar-grid">
							{cells.map((day, i) => {
								if (day === null) {
									return <div key={`pad-${i}`} className="calendar-day calendar-day--pad" />;
								}
								const evs = eventsOnDay(events, year, month0, day);
								const today = isToday(year, month0, day);
								return (
									<div
										key={toYmd(year, month0, day)}
										className={`calendar-day${today ? " calendar-day--today" : ""}`}
									>
										<div className="calendar-day-num">{day}</div>
										<div className="calendar-day-events">
											<EventBlocks events={evs} />
										</div>
									</div>
								);
							})}
						</div>
					</>
				) : null}

				{viewMode === "week" ? (
					<CalendarTimeGrid days={weekDays} events={events} isTodayColumn={isTodayCol} />
				) : null}

				{viewMode === "day" ? (
					<CalendarTimeGrid days={[cursor]} events={events} isTodayColumn={isTodayCol} />
				) : null}
			</section>
		</div>
	);
}
