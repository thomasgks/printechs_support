import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getPortalTickets, portalTicketNewPath, portalTicketPath } from "../api";

function fmtListDateTime(v: unknown): string {
	const s = String(v ?? "").trim();
	return s ? s.slice(0, 16) : "—";
}

export default function TicketsPage() {
	const [searchParams, setSearchParams] = useSearchParams();
	const qFromUrl = (searchParams.get("q") ?? "").trim();
	const [rows, setRows] = useState<Record<string, unknown>[]>([]);
	const [err, setErr] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [searchDraft, setSearchDraft] = useState(qFromUrl);
	const [appliedSearch, setAppliedSearch] = useState(qFromUrl);
	/** false = active only; true = include resolved/closed/cancelled */
	const [showAll, setShowAll] = useState(false);

	// Sync from URL ?q= (header search or shared links)
	useEffect(() => {
		setSearchDraft(qFromUrl);
		setAppliedSearch(qFromUrl);
	}, [qFromUrl]);

	const load = useCallback(async () => {
		setErr(null);
		setLoading(true);
		try {
			const data = await getPortalTickets(200, {
				search: appliedSearch.trim() || undefined,
				activeOnly: !showAll,
			});
			setRows(data);
		} catch (e) {
			setErr(e instanceof Error ? e.message : "Failed to load");
		} finally {
			setLoading(false);
		}
	}, [appliedSearch, showAll]);

	useEffect(() => {
		void load();
	}, [load]);

	const applySearch = () => {
		const q = searchDraft.trim();
		setAppliedSearch(q);
		setSearchParams(q ? { q } : {});
	};

	const clearFilters = () => {
		setSearchDraft("");
		setAppliedSearch("");
		setShowAll(false);
		setSearchParams({});
	};

	if (loading && rows.length === 0 && !err) {
		return (
			<div className="flex flex-col gap-4">
				<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">Tickets</h1>
				<p className="muted">Loading tickets…</p>
			</div>
		);
	}

	if (err) {
		return (
			<div className="flex flex-col gap-4">
				<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">Tickets</h1>
				<p className="error-text">{err}</p>
			</div>
		);
	}

	const hasRows = rows.length > 0;

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">Tickets</h1>
				<Link to={portalTicketNewPath()} className="portal-btn-primary inline-flex rounded-xl px-5 py-2.5 text-sm font-bold">
					New ticket
				</Link>
			</div>

			<div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
				<p className="text-xs font-bold uppercase tracking-wide text-slate-500">Filters</p>
				<div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end lg:justify-between">
					<div className="flex min-w-0 flex-1 flex-col gap-1">
						<label htmlFor="ticket-search-id" className="text-xs font-semibold text-slate-600">
							Ticket ID contains
						</label>
						<input
							id="ticket-search-id"
							type="search"
							placeholder="e.g. SUP-TKT-2026-00027"
							className="w-full max-w-md rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900 shadow-inner outline-none ring-violet-500/20 placeholder:text-slate-400 focus:border-violet-400 focus:ring-4"
							value={searchDraft}
							onChange={(e) => setSearchDraft(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") {
									applySearch();
								}
							}}
						/>
					</div>
					<div className="flex min-w-[14rem] flex-col gap-1">
						<label htmlFor="ticket-scope" className="text-xs font-semibold text-slate-600">
							Which tickets to list
						</label>
						<select
							id="ticket-scope"
							className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-inner outline-none focus:border-violet-400 focus:ring-4"
							value={showAll ? "all" : "active"}
							onChange={(e) => setShowAll(e.target.value === "all")}
						>
							<option value="active">Active only (hide resolved, closed, cancelled)</option>
							<option value="all">All statuses</option>
						</select>
					</div>
					<div className="flex flex-wrap items-center gap-2">
						<button
							type="button"
							className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-indigo-700"
							onClick={() => applySearch()}
						>
							Apply filters
						</button>
						<button
							type="button"
							className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-bold text-slate-800 hover:bg-slate-100"
							onClick={() => clearFilters()}
						>
							Clear
						</button>
					</div>
				</div>
				<p className="text-xs text-slate-500">
					{showAll
						? "Listing every status that you are allowed to see."
						: "Hiding resolved, closed, and cancelled — switch to “All statuses” to include them."}
					{loading ? <span className="ml-2 font-semibold text-violet-600">Refreshing…</span> : null}
				</p>
			</div>

			{!hasRows ? (
				<div className="empty-state rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-10">
					<p className="font-semibold text-slate-900">No tickets match these filters.</p>
					<p className="muted small mt-2">
						Try <strong className="font-semibold text-slate-700">All statuses</strong>, clear the ID search, or use{" "}
						<strong className="font-semibold text-slate-700">Clear</strong> above.
					</p>
					<p className="mt-4">
						<Link to={portalTicketNewPath()} className="portal-btn-primary inline-block rounded-xl px-5 py-2.5 text-sm font-bold">
							New ticket
						</Link>
					</p>
				</div>
			) : (
				<div className={`table-wrap ${loading ? "opacity-70" : ""}`}>
					<table className="data-table">
						<thead>
							<tr>
								<th>ID</th>
								<th>Subject</th>
								<th>Customer</th>
								<th>Status</th>
								<th>Priority</th>
								<th>Due Date</th>
								<th>Updated</th>
							</tr>
						</thead>
						<tbody>
							{rows.map((r) => (
								<tr key={String(r.name)}>
									<td>
										<Link to={portalTicketPath(String(r.name))} className="id-link">
											{r.name as string}
										</Link>
									</td>
									<td>{(r.subject as string) || "—"}</td>
									<td className="muted">{String(r.customer ?? "—")}</td>
									<td>
										<span className="pill">{String(r.status ?? "")}</span>
									</td>
									<td>{String(r.priority ?? "—")}</td>
									<td className="muted">{fmtListDateTime(r.due_date)}</td>
									<td className="muted">{fmtListDateTime(r.modified)}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
