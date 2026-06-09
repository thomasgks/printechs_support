import { useEffect, useMemo, useState } from "react";
import { getPortalTaskComments, getPortalTicketComments, type PortalComment } from "../api";
import { portalCommentAnchorId } from "../lib/commentAnchors";

type Mode = "ticket" | "task";

type Props = {
	mode: Mode;
	name: string;
	doc: Record<string, unknown>;
};

type HistoryEvent = {
	key: string;
	at: string | null;
	title: string;
	meta: string;
	body?: string;
	scope?: string;
	anchorId?: string;
};

function asText(v: unknown): string {
	return String(v ?? "").trim();
}

function firstDate(...values: unknown[]): string | null {
	for (const v of values) {
		const s = asText(v);
		if (s) return s;
	}
	return null;
}

function stripHtml(html: string): string {
	const withBreaks = html
		.replace(/<br\s*\/?>/gi, "\n")
		.replace(/<\/p>/gi, "\n")
		.replace(/<\/div>/gi, "\n")
		.replace(/<\/li>/gi, "\n");
	const text = withBreaks.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
	return text.length > 220 ? `${text.slice(0, 219).trim()}…` : text;
}

function parseTime(v: string | null): number | null {
	if (!v) return null;
	const s = v.trim();
	const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
	if (m) {
		const [, year, month, day, hour = "00", minute = "00", second = "00"] = m;
		const t = new Date(
			Number(year),
			Number(month) - 1,
			Number(day),
			Number(hour),
			Number(minute),
			Number(second),
		).getTime();
		return Number.isNaN(t) ? null : t;
	}
	const t = Date.parse(s);
	return Number.isNaN(t) ? null : t;
}

function formatDateTime(v: string | null): string {
	return v ? v.slice(0, 16) : "—";
}

function durationLabel(from: string | null, to: string | null): string {
	const a = parseTime(from);
	const b = parseTime(to);
	if (a == null || b == null || b < a) return "";
	const diffMs = b - a;
	if (diffMs < 60000) return "<1m";
	const mins = Math.floor(diffMs / 60000);
	if (mins < 60) return `${mins}m`;
	const hours = Math.floor(mins / 60);
	if (hours < 48) return `${hours}h`;
	const days = Math.floor(hours / 24);
	return `${days}d`;
}

function eventSort(a: HistoryEvent, b: HistoryEvent): number {
	const ta = parseTime(a.at) ?? 0;
	const tb = parseTime(b.at) ?? 0;
	return ta - tb || a.key.localeCompare(b.key);
}

function commentTitle(row: PortalComment): string {
	const rawType = asText(row.comment_type);
	const type =
		asText(row.display_comment_type) ||
		(row.author_is_internal && row.is_customer_visible && ["", "Comment", "Reply", "Customer Reply"].includes(rawType)
			? "Technician"
			: row.is_customer_visible && ["", "Comment", "Reply", "Customer Reply"].includes(rawType)
				? "Customer"
			: rawType || "Communication");
	const author = asText(row.author_name || row.comment_by) || "Unknown";
	return `${type} by ${author}`;
}

function commentMeta(row: PortalComment): string {
	const parts = [row.thread_scope === "task" ? `Task: ${row.task_subject || row.task_name}` : "", row.internal_only ? "Internal" : "Customer visible"];
	return parts.filter(Boolean).join(" · ");
}

export default function HistorySummaryPanel({ mode, name, doc }: Props) {
	const [comments, setComments] = useState<PortalComment[]>([]);
	const [loading, setLoading] = useState(true);
	const [err, setErr] = useState<string | null>(null);
	const [expanded, setExpanded] = useState(false);
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

	useEffect(() => {
		let cancelled = false;
		setLoading(true);
		setErr(null);
		(mode === "ticket" ? getPortalTicketComments(name) : getPortalTaskComments(name))
			.then((rows) => {
				if (!cancelled) setComments(rows ?? []);
			})
			.catch((e) => {
				if (!cancelled) setErr(e instanceof Error ? e.message : "Could not load history");
			})
			.finally(() => {
				if (!cancelled) setLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [mode, name]);

	const createdOn = mode === "ticket" ? firstDate(doc.opening_date, doc.creation) : firstDate(doc.creation, doc.planned_start_date);
	const resolvedOn = mode === "ticket" ? firstDate(doc.resolved_on) : firstDate(doc.actual_end_date);
	const closedOn = mode === "ticket" ? firstDate(doc.closed_on) : null;
	const finalOn = firstDate(closedOn, resolvedOn, doc.modified);

	const events = useMemo(() => {
		const rows: HistoryEvent[] = [];
		if (createdOn) {
			rows.push({
				key: "created",
				at: createdOn,
				title: mode === "ticket" ? "Ticket created" : "Task created",
				meta: asText(doc.customer || doc.customer_name || doc.ticket_subject),
				body: asText(doc.subject),
				scope: mode,
			});
		}
		for (const row of comments) {
			rows.push({
				key: `comment-${row.thread_scope || mode}-${row.name || row.comment_on}`,
				at: row.comment_on,
				title: commentTitle(row),
				meta: commentMeta(row),
				body: stripHtml(row.content || ""),
				scope: row.thread_scope || mode,
				anchorId: row.comment_type === "System Update" ? undefined : portalCommentAnchorId(row),
			});
		}
		if (resolvedOn) {
			rows.push({
				key: "resolved",
				at: resolvedOn,
				title: mode === "ticket" ? "Ticket resolved" : "Task completed",
				meta: asText(doc.resolution_type || doc.status),
				body: stripHtml(asText(doc.resolution_summary_html || "")),
				scope: mode,
			});
		}
		if (closedOn) {
			rows.push({
				key: "closed",
				at: closedOn,
				title: "Ticket closed",
				meta: asText(doc.status),
				scope: mode,
			});
		}
		return rows.sort(eventSort);
	}, [closedOn, comments, createdOn, doc, mode, resolvedOn]);

	const visibleEvents = sortDirection === "asc" ? events : [...events].reverse();
	const totalDuration = durationLabel(createdOn, finalOn);

	return (
		<section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-saas">
			<div className="mb-4 flex flex-wrap items-start justify-between gap-3">
				<div>
					<p className="text-xs font-bold uppercase tracking-[0.18em] text-violet-600">History summary</p>
					<h2 className="mt-1 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">
						Full read-only timeline
					</h2>
				</div>
				<div className="flex flex-wrap items-center gap-2">
					<span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700 ring-1 ring-slate-200">
						{events.length} event(s)
					</span>
					<button
						type="button"
						className={`rounded-full px-3 py-1 text-xs font-bold shadow-sm ring-1 ${
							sortDirection === "asc"
								? "bg-violet-50 text-violet-800 ring-violet-200"
								: "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50"
						}`}
						aria-pressed={sortDirection === "asc"}
						onClick={() => setSortDirection("asc")}
					>
						Ascending
					</button>
					<button
						type="button"
						className={`rounded-full px-3 py-1 text-xs font-bold shadow-sm ring-1 ${
							sortDirection === "desc"
								? "bg-violet-50 text-violet-800 ring-violet-200"
								: "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50"
						}`}
						aria-pressed={sortDirection === "desc"}
						onClick={() => setSortDirection("desc")}
					>
						Descending
					</button>
					<button
						type="button"
						className="rounded-full bg-violet-600 px-3 py-1 text-xs font-bold text-white shadow-sm hover:bg-violet-700"
						aria-expanded={expanded}
						onClick={() => setExpanded((v) => !v)}
					>
						{expanded ? "Collapse" : "Expand"}
					</button>
				</div>
			</div>

			<div className="mb-5 grid gap-3 sm:grid-cols-3">
				<div className="rounded-2xl bg-slate-50 px-4 py-3">
					<p className="text-xs font-bold uppercase tracking-wide text-slate-500">Created</p>
					<p className="mt-1 font-semibold text-slate-900">{formatDateTime(createdOn)}</p>
				</div>
				<div className="rounded-2xl bg-slate-50 px-4 py-3">
					<p className="text-xs font-bold uppercase tracking-wide text-slate-500">Current status</p>
					<p className="mt-1 font-semibold text-slate-900">{asText(doc.status) || "—"}</p>
				</div>
				<div className="rounded-2xl bg-slate-50 px-4 py-3">
					<p className="text-xs font-bold uppercase tracking-wide text-slate-500">Total time</p>
					<p className="mt-1 font-semibold text-slate-900">{totalDuration || "In progress"}</p>
				</div>
			</div>

			{!expanded ? (
				<p className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-3 text-sm text-slate-600">
					Timeline is collapsed. Click <strong>Expand</strong> to view every communication and time gap.
				</p>
			) : null}

			{expanded && err ? <p className="rounded-xl bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{err}</p> : null}
			{expanded && loading ? <p className="text-sm text-slate-600">Loading history…</p> : null}
			{expanded && !loading && !events.length ? <p className="text-sm text-slate-600">No history available yet.</p> : null}

			{expanded && !loading && visibleEvents.length ? (
				<ol className="space-y-3">
					{visibleEvents.map((event, index) => {
						const prev = index > 0 ? visibleEvents[index - 1] : null;
						const gap = prev ? (sortDirection === "asc" ? durationLabel(prev.at, event.at) : durationLabel(event.at, prev.at)) : "";
						const elapsedLabel = gap ? (sortDirection === "asc" ? `Updated after ${gap}` : `Updated before ${gap}`) : "";
						return (
							<li key={event.key} className="rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-3">
								<div className="flex flex-wrap items-start justify-between gap-2">
									<div>
										<p className="font-semibold text-slate-900">{event.title}</p>
										<p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
											<span>{formatDateTime(event.at)}</span>
											{elapsedLabel ? <span className="font-bold text-violet-700">{elapsedLabel}</span> : null}
											{event.meta ? <span>{event.meta}</span> : null}
										</p>
									</div>
									{event.scope ? (
										<span className="rounded-full bg-white px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-wide text-slate-500 ring-1 ring-slate-200">
											{event.scope}
										</span>
									) : null}
								</div>
								{event.body ? <p className="mt-2 text-sm text-slate-700">{event.body}</p> : null}
								{event.anchorId ? (
									<a
										href={`#${event.anchorId}`}
										className="mt-2 inline-flex text-xs font-bold text-violet-700 underline decoration-violet-200 underline-offset-2 hover:text-violet-900"
									>
										View in conversation
									</a>
								) : null}
							</li>
						);
					})}
				</ol>
			) : null}
		</section>
	);
}
