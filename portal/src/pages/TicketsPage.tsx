import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getPortalTicketCustomers, getPortalTickets, getPortalTicketTypes, portalTicketNewPath, portalTicketPath } from "../api";
import type { PortalTicketCustomerRow, PortalTicketTypeRow } from "../api";

function fmtListDateTime(v: unknown): string {
	const s = String(v ?? "").trim();
	return s ? s.slice(0, 16) : "—";
}

export default function TicketsPage() {
	const [searchParams, setSearchParams] = useSearchParams();
	const qFromUrl = (searchParams.get("q") ?? "").trim();
	const customerFromUrl = (searchParams.get("customer") ?? "").trim();
	const ticketTypeFromUrl = (searchParams.get("ticket_type") ?? "").trim();
	const [rows, setRows] = useState<Record<string, unknown>[]>([]);
	const [customerRows, setCustomerRows] = useState<PortalTicketCustomerRow[]>([]);
	const [ticketTypeRows, setTicketTypeRows] = useState<PortalTicketTypeRow[]>([]);
	const [ticketTypesLoaded, setTicketTypesLoaded] = useState(false);
	const [err, setErr] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [searchDraft, setSearchDraft] = useState(qFromUrl);
	const [appliedSearch, setAppliedSearch] = useState(qFromUrl);
	const [customerDraft, setCustomerDraft] = useState(customerFromUrl);
	const [appliedCustomer, setAppliedCustomer] = useState(customerFromUrl);
	const [ticketTypeDraft, setTicketTypeDraft] = useState(ticketTypeFromUrl);
	const [appliedTicketType, setAppliedTicketType] = useState(ticketTypeFromUrl);
	/** false = active only; true = include resolved/closed/cancelled */
	const [showAll, setShowAll] = useState(false);

	// Sync from URL ?q= / ?customer= (header search or shared links)
	useEffect(() => {
		setSearchDraft(qFromUrl);
		setAppliedSearch(qFromUrl);
		setCustomerDraft(customerFromUrl);
		setAppliedCustomer(customerFromUrl);
		setTicketTypeDraft(ticketTypeFromUrl);
		setAppliedTicketType(ticketTypeFromUrl);
	}, [qFromUrl, customerFromUrl, ticketTypeFromUrl]);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				const data = await getPortalTicketCustomers();
				if (!cancelled) {
					setCustomerRows(data.customers ?? []);
				}
			} catch {
				if (!cancelled) {
					setCustomerRows([]);
				}
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	const load = useCallback(async () => {
		setErr(null);
		setLoading(true);
		try {
			const data = await getPortalTickets(200, {
				search: appliedSearch.trim() || undefined,
				customer: appliedCustomer.trim() || undefined,
				ticketType: appliedTicketType.trim() || undefined,
				activeOnly: !showAll,
			});
			setRows(data);
		} catch (e) {
			setErr(e instanceof Error ? e.message : "Failed to load");
		} finally {
			setLoading(false);
		}
	}, [appliedCustomer, appliedSearch, appliedTicketType, showAll]);

	useEffect(() => {
		void load();
	}, [load]);

	const applySearch = () => {
		const q = searchDraft.trim();
		const customer = customerDraft.trim();
		const ticketType = ticketTypeDraft.trim();
		setAppliedSearch(q);
		setAppliedCustomer(customer);
		setAppliedTicketType(ticketType);
		const nextParams: Record<string, string> = {};
		if (q) nextParams.q = q;
		if (customer) nextParams.customer = customer;
		if (ticketType) nextParams.ticket_type = ticketType;
		setSearchParams(nextParams);
	};

	const clearFilters = () => {
		setSearchDraft("");
		setAppliedSearch("");
		setCustomerDraft("");
		setAppliedCustomer("");
		setTicketTypeDraft("");
		setAppliedTicketType("");
		setShowAll(false);
		setSearchParams({});
	};

	const customerOptions = useMemo(() => {
		const labels = new Map<string, string>();
		for (const row of customerRows) {
			const name = String(row.name ?? "").trim();
			if (name) {
				labels.set(name, String(row.customer_name || name).trim());
			}
		}
		for (const row of rows) {
			const name = String(row.customer ?? "").trim();
			if (name && !labels.has(name)) {
				labels.set(name, name);
			}
		}
		if (customerDraft && !labels.has(customerDraft)) {
			labels.set(customerDraft, customerDraft);
		}
		return Array.from(labels, ([name, label]) => ({ name, label })).sort((a, b) => a.label.localeCompare(b.label));
	}, [customerDraft, customerRows, rows]);

	const selectedCustomerName = useMemo(() => {
		const raw = customerDraft.trim();
		if (!raw) {
			return "";
		}
		const rawLower = raw.toLowerCase();
		for (const row of customerRows) {
			const name = String(row.name ?? "").trim();
			const label = String(row.customer_name || name).trim();
			if (name.toLowerCase() === rawLower || label.toLowerCase() === rawLower) {
				return name;
			}
		}
		return "";
	}, [customerDraft, customerRows]);

	useEffect(() => {
		let cancelled = false;
		setTicketTypesLoaded(false);
		(async () => {
			try {
				const data = await getPortalTicketTypes(selectedCustomerName || undefined);
				if (!cancelled) {
					setTicketTypeRows(data.types ?? []);
					setTicketTypesLoaded(true);
				}
			} catch {
				if (!cancelled) {
					setTicketTypeRows([]);
					setTicketTypesLoaded(true);
				}
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [selectedCustomerName]);

	useEffect(() => {
		if (!ticketTypesLoaded || !ticketTypeDraft) {
			return;
		}
		if (!ticketTypeRows.some((row) => row.name === ticketTypeDraft)) {
			setTicketTypeDraft("");
			setAppliedTicketType("");
			setSearchParams((prev) => {
				const next = new URLSearchParams(prev);
				next.delete("ticket_type");
				return next;
			});
		}
	}, [setSearchParams, ticketTypeDraft, ticketTypeRows, ticketTypesLoaded]);

	const ticketTypeOptions = useMemo(() => {
		const labels = new Map<string, string>();
		for (const row of ticketTypeRows) {
			const name = String(row.name ?? "").trim();
			if (name) {
				labels.set(name, String(row.label || name).trim());
			}
		}
		if (!selectedCustomerName) {
			for (const row of rows) {
				const name = String(row.ticket_type ?? "").trim();
				if (name && !labels.has(name)) {
					labels.set(name, String(row.ticket_type_label || name).trim());
				}
			}
		}
		if (ticketTypeDraft && !labels.has(ticketTypeDraft)) {
			labels.set(ticketTypeDraft, ticketTypeDraft);
		}
		return Array.from(labels, ([name, label]) => ({ name, label })).sort((a, b) => a.label.localeCompare(b.label));
	}, [rows, selectedCustomerName, ticketTypeDraft, ticketTypeRows]);

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
				<div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(11rem,0.8fr)_minmax(13rem,1fr)_minmax(12rem,0.9fr)_minmax(10rem,0.8fr)_auto] xl:items-end">
					<div className="flex min-w-0 flex-col gap-1">
						<label htmlFor="ticket-search-id" className="text-xs font-semibold text-slate-600">
							Ticket ID
						</label>
						<input
							id="ticket-search-id"
							type="search"
							placeholder="SUP-TKT-2026-00027"
							className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900 shadow-inner outline-none ring-violet-500/20 placeholder:text-slate-400 focus:border-violet-400 focus:ring-4"
							value={searchDraft}
							onChange={(e) => setSearchDraft(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") {
									applySearch();
								}
							}}
						/>
					</div>
					<div className="flex min-w-0 flex-col gap-1">
						<label htmlFor="ticket-customer" className="text-xs font-semibold text-slate-600">
							Customer
						</label>
						<input
							id="ticket-customer"
							type="search"
							list="ticket-customer-options"
							placeholder="Customer name..."
							className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-inner outline-none ring-violet-500/20 placeholder:text-slate-400 focus:border-violet-400 focus:ring-4"
							value={customerDraft}
							onChange={(e) => setCustomerDraft(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") {
									applySearch();
								}
							}}
						/>
						<datalist id="ticket-customer-options">
							{customerOptions.map((c) => (
								<option key={c.name} value={c.label} />
							))}
						</datalist>
					</div>
					<div className="flex min-w-0 flex-col gap-1">
						<label htmlFor="ticket-type-filter" className="text-xs font-semibold text-slate-600">
							Ticket type
						</label>
						<select
							id="ticket-type-filter"
							className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-inner outline-none focus:border-violet-400 focus:ring-4"
							value={ticketTypeDraft}
							onChange={(e) => setTicketTypeDraft(e.target.value)}
						>
							<option value="">All types</option>
							{ticketTypeOptions.map((t) => (
								<option key={t.name} value={t.name}>
									{t.label}
								</option>
							))}
						</select>
					</div>
					<div className="flex min-w-0 flex-col gap-1">
						<label htmlFor="ticket-scope" className="text-xs font-semibold text-slate-600">
							Status
						</label>
						<select
							id="ticket-scope"
							className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-inner outline-none focus:border-violet-400 focus:ring-4"
							value={showAll ? "all" : "active"}
							onChange={(e) => setShowAll(e.target.value === "all")}
						>
							<option value="active">Active only</option>
							<option value="all">All statuses</option>
						</select>
					</div>
					<div className="flex flex-wrap items-center gap-2 md:col-span-2 xl:col-span-1">
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
					{appliedCustomer ? <span className="ml-2 font-semibold text-slate-600">Customer filter is active.</span> : null}
					{appliedTicketType ? <span className="ml-2 font-semibold text-slate-600">Ticket type filter is active.</span> : null}
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
								<th>Type</th>
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
									<td className="muted">{String(r.ticket_type_label || r.ticket_type || "—")}</td>
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
