import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { portalTicketPath } from "../api";
import {
	CAL_PX_PER_HOUR,
	CAL_TIME_END_H,
	CAL_TIME_START_H,
	dateToYmd,
	type CalendarEventItem,
	parseTimeToMinutes,
} from "../calendarUtils";

function eventLinkTo(ev: CalendarEventItem): string | null {
	if (ev.href?.trim()) {
		return ev.href;
	}
	if (ev.ticket?.trim()) {
		return portalTicketPath(ev.ticket);
	}
	return null;
}

function endMinutes(ev: CalendarEventItem): number {
	const s = parseTimeToMinutes(ev.start);
	if (s === null) {
		return 0;
	}
	const e = parseTimeToMinutes(ev.end);
	if (e !== null) {
		return Math.max(e, s + 15);
	}
	return s + 30;
}

function formatHour12(h: number): string {
	if (h === 0) {
		return "12 AM";
	}
	if (h < 12) {
		return `${h} AM`;
	}
	if (h === 12) {
		return "12 PM";
	}
	return `${h - 12} PM`;
}

const WEEK_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Props = {
	days: Date[];
	events: CalendarEventItem[];
	isTodayColumn: (d: Date) => boolean;
};

export default function CalendarTimeGrid({ days, events, isTodayColumn }: Props) {
	const headGridCols = `52px repeat(${days.length}, minmax(0, 1fr))`;
	const [tick, setTick] = useState(0);
	useEffect(() => {
		const id = window.setInterval(() => setTick((t) => t + 1), 60_000);
		return () => window.clearInterval(id);
	}, []);

	const hours = useMemo(
		() => Array.from({ length: CAL_TIME_END_H - CAL_TIME_START_H }, (_, i) => CAL_TIME_START_H + i),
		[],
	);

	const trackHeight = (CAL_TIME_END_H - CAL_TIME_START_H) * CAL_PX_PER_HOUR;

	const nowTop = useMemo(() => {
		const n = new Date();
		const mins = n.getHours() * 60 + n.getMinutes();
		const start = CAL_TIME_START_H * 60;
		const end = CAL_TIME_END_H * 60;
		if (mins < start || mins > end) {
			return null;
		}
		return ((mins - start) / 60) * CAL_PX_PER_HOUR;
	}, [tick]);

	return (
		<div className="cal-tg">
			<div className="cal-tg-head" style={{ gridTemplateColumns: headGridCols }}>
				<div className="cal-tg-corner" aria-hidden />
				{days.map((d) => {
					const ymd = dateToYmd(d);
					const today = isTodayColumn(d);
					return (
						<div key={`h-${ymd}`} className={`cal-tg-head-cell${today ? " cal-tg-head-cell--today" : ""}`}>
							<span className="cal-tg-head-dow">{WEEK_LABELS[(d.getDay() + 6) % 7]}</span>
							<span className="cal-tg-head-dom">{d.getDate()}</span>
						</div>
					);
				})}
			</div>

			<div className="cal-tg-allday-row" style={{ gridTemplateColumns: headGridCols }}>
				<div className="cal-tg-allday-gutter">All-day</div>
				{days.map((d) => {
					const ymd = dateToYmd(d);
					const allDay = events.filter((e) => e.date === ymd && !e.start);
					return (
						<div key={`ad-${ymd}`} className="cal-tg-allday-cell">
							{allDay.map((ev, i) => {
								const ln = eventLinkTo(ev);
								return (
									<div
										key={`${ymd}-ad-${i}-${ev.id ?? ev.title}`}
										className={`cal-tg-allday-chip cal-tg-allday-chip--${ev.color ?? "purple"}`}
										title={ev.title}
									>
										{ln ? <Link to={ln}>{ev.title}</Link> : ev.title}
									</div>
								);
							})}
						</div>
					);
				})}
			</div>

			<div className="cal-tg-scroll">
				<div className="cal-tg-inner" style={{ display: "grid", gridTemplateColumns: headGridCols }}>
					<div className="cal-tg-gutter" aria-hidden>
						{hours.map((h) => (
							<div key={h} className="cal-tg-gutter-hour" style={{ height: CAL_PX_PER_HOUR }}>
								{formatHour12(h)}
							</div>
						))}
					</div>
					{days.map((d) => {
						const ymd = dateToYmd(d);
						const timed = events.filter((e) => e.date === ymd && e.start);
						const showNow = nowTop !== null && isTodayColumn(d);

						return (
							<div key={ymd} className="cal-tg-col">
								<div className="cal-tg-track" style={{ height: trackHeight }}>
									{hours.map((h) => (
										<div key={h} className="cal-tg-slot" style={{ height: CAL_PX_PER_HOUR }} />
									))}
									{timed.map((ev, i) => {
										const sm = parseTimeToMinutes(ev.start);
										if (sm === null) {
											return null;
										}
										const em = endMinutes(ev);
										const startM = CAL_TIME_START_H * 60;
										const top = ((sm - startM) / 60) * CAL_PX_PER_HOUR;
										const hgt = Math.max(((em - sm) / 60) * CAL_PX_PER_HOUR, 24);
										const ln = eventLinkTo(ev);
										return (
											<div
												key={`${ymd}-t-${i}-${ev.id ?? ev.title}`}
												className={`cal-tg-event cal-tg-event--${ev.color ?? "purple"}`}
												style={{ top, height: hgt }}
												title={ev.title}
											>
												<div className="cal-tg-event-time">
													{ev.start}
													{ev.end ? ` – ${ev.end}` : ""}
												</div>
												<div className="cal-tg-event-title">
													{ln ? <Link to={ln}>{ev.title}</Link> : ev.title}
												</div>
											</div>
										);
									})}
									{showNow ? (
										<div className="cal-tg-now" style={{ top: nowTop }}>
											<span className="cal-tg-now-label">
												{new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
											</span>
										</div>
									) : null}
								</div>
							</div>
						);
					})}
				</div>
			</div>
		</div>
	);
}
