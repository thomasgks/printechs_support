import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getPortalBootstrap, getPortalTasks, portalTaskNewPath, portalTaskPath, portalTicketPath, type PortalTaskSort } from "../api";
import { formatPortalAssignees } from "../lib/assignees";
import { statusBadgeClasses } from "../lib/status";
import {
	PORTAL_TASK_SORT_OPTIONS,
	readPortalTaskSortPreference,
	writePortalTaskSortPreference,
} from "../lib/taskSort";

const TERMINAL = new Set(["Completed", "Cancelled"]);

function ageDays(creation: unknown, due: unknown, status: string): string {
	if (TERMINAL.has(status)) return "—";
	if (!creation) return "—";
	const t = new Date(String(creation));
	if (Number.isNaN(t.getTime())) return "—";
	const days = Math.floor((Date.now() - t.getTime()) / 86400000);
	let s = `${days}d`;
	if (due) {
		const d = new Date(String(due));
		if (!Number.isNaN(d.getTime()) && d < new Date()) s += " · overdue";
	}
	return s;
}

const KANBAN_ORDER = [
	"Open",
	"In Progress",
	"Waiting for Customer",
	"Waiting for Printechs",
	"Completed",
] as const;

export default function TasksPage() {
	const [rows, setRows] = useState<Record<string, unknown>[]>([]);
	const [err, setErr] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [view, setView] = useState<"table" | "kanban">("table");
	const [filterStatus, setFilterStatus] = useState("");
	const [filterCustomer, setFilterCustomer] = useState("");
	const [filterDelayOwner, setFilterDelayOwner] = useState("");
	const [sortBy, setSortBy] = useState<PortalTaskSort>(() => readPortalTaskSortPreference());
	const [internalUser, setInternalUser] = useState(false);

	useEffect(() => {
		let c = false;
		setLoading(true);
		(async () => {
			try {
				const [data, boot] = await Promise.all([getPortalTasks(100, sortBy), getPortalBootstrap()]);
				if (!c) {
					setRows(data);
					if (boot.logged_in && "internal" in boot) {
						setInternalUser(Boolean(boot.internal));
					}
				}
			} catch (e) {
				if (!c) {
					setErr(e instanceof Error ? e.message : "Failed to load");
				}
			} finally {
				if (!c) {
					setLoading(false);
				}
			}
		})();
		return () => {
			c = true;
		};
	}, [sortBy]);

	function onSortChange(next: PortalTaskSort) {
		setSortBy(next);
		writePortalTaskSortPreference(next);
	}

	const customers = useMemo(() => {
		const s = new Set<string>();
		for (const r of rows) {
			const c = r.customer;
			if (c) s.add(String(c));
		}
		return Array.from(s).sort();
	}, [rows]);

	const delayOwners = useMemo(() => {
		const s = new Set<string>();
		for (const r of rows) {
			s.add(String(r.delay_owner ?? ""));
		}
		return Array.from(s).sort((a, b) => a.localeCompare(b));
	}, [rows]);

	const filtered = useMemo(() => {
		return rows.filter((r) => {
			if (filterStatus && String(r.status) !== filterStatus) return false;
			if (filterCustomer && String(r.customer ?? "") !== filterCustomer) return false;
			if (filterDelayOwner && String(r.delay_owner ?? "") !== filterDelayOwner) return false;
			return true;
		});
	}, [rows, filterStatus, filterCustomer, filterDelayOwner]);

	const kanbanGrouped = useMemo(() => {
		const m = new Map<string, Record<string, unknown>[]>();
		for (const k of KANBAN_ORDER) {
			m.set(k, []);
		}
		m.set("Other", []);
		for (const r of filtered) {
			const st = String(r.status ?? "");
			if (m.has(st)) {
				m.get(st)!.push(r);
			} else {
				m.get("Other")!.push(r);
			}
		}
		return m;
	}, [filtered]);

	if (loading) {
		return <p className="muted">Loading tasks…</p>;
	}
	if (err) {
		return <p className="error-text">{err}</p>;
	}
	if (!rows.length) {
		return (
			<div className="empty-state rounded-2xl">
				<p>No tasks visible yet.</p>
				<p className="muted small">Tasks appear when linked to tickets you can access.</p>
				{internalUser ? (
					<p className="mt-3">
						<Link to={portalTaskNewPath()} className="inline-flex rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700">
							New task
						</Link>
						<span className="muted ml-2 text-sm">(internal — link a task to a ticket)</span>
					</p>
				) : (
					<p className="muted mt-2 text-sm">Internal users can create tasks from the portal; customers work at ticket level.</p>
				)}
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-wrap items-end justify-between gap-3">
				<div>
					<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">Tasks</h1>
					<p className="text-sm text-slate-500">Table and Kanban share the same data (portal scope).</p>
				</div>
				<div className="flex flex-wrap gap-2">
					{internalUser ? (
						<Link
							to={portalTaskNewPath()}
							className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
						>
							New task
						</Link>
					) : null}
					<button
						type="button"
						className={`rounded-xl border px-4 py-2 text-sm font-semibold shadow-sm ${
							view === "table"
								? "border-blue-400 bg-blue-600 text-white"
								: "border-slate-200 bg-white text-slate-700 hover:border-blue-200"
						}`}
						onClick={() => setView("table")}
					>
						Table
					</button>
					<button
						type="button"
						className={`rounded-xl border px-4 py-2 text-sm font-semibold shadow-sm ${
							view === "kanban"
								? "border-blue-400 bg-blue-600 text-white"
								: "border-slate-200 bg-white text-slate-700 hover:border-blue-200"
						}`}
						onClick={() => setView("kanban")}
					>
						Kanban
					</button>
					<Link
						to="/calendar"
						className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-blue-200"
					>
						Calendar
					</Link>
				</div>
			</div>

			<div className="flex flex-wrap gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-saas">
				<label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
					Status
					<select
						className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-slate-900"
						value={filterStatus}
						onChange={(e) => setFilterStatus(e.target.value)}
					>
						<option value="">All</option>
						{Array.from(new Set(rows.map((r) => String(r.status ?? ""))))
							.filter(Boolean)
							.sort()
							.map((s) => (
								<option key={s} value={s}>
									{s}
								</option>
							))}
					</select>
				</label>
				<label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
					Customer
					<select
						className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-slate-900"
						value={filterCustomer}
						onChange={(e) => setFilterCustomer(e.target.value)}
					>
						<option value="">All</option>
						{customers.map((c) => (
							<option key={c} value={c}>
								{c}
							</option>
						))}
					</select>
				</label>
				<label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
					Delay owner
					<select
						className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-slate-900"
						value={filterDelayOwner}
						onChange={(e) => setFilterDelayOwner(e.target.value)}
					>
						<option value="">All</option>
						{delayOwners.map((x) => (
							<option key={x || "empty"} value={x}>
								{x || "(empty)"}
							</option>
						))}
					</select>
				</label>
				<fieldset className="flex min-w-[220px] flex-col gap-2 border-0 p-0">
					<legend className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sort by</legend>
					<div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Sort tasks">
						{PORTAL_TASK_SORT_OPTIONS.map((opt) => (
							<label
								key={opt.value}
								className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium shadow-sm ${
									sortBy === opt.value
										? "border-blue-400 bg-blue-50 text-blue-900"
										: "border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200"
								}`}
							>
								<input
									type="radio"
									name="task-sort"
									className="h-4 w-4 border-slate-300 text-blue-600 focus:ring-blue-500"
									checked={sortBy === opt.value}
									onChange={() => onSortChange(opt.value)}
								/>
								{opt.label}
								{opt.default ? (
									<span className="text-xs font-normal text-slate-500">(default)</span>
								) : null}
							</label>
						))}
					</div>
				</fieldset>
			</div>

			{view === "table" ? (
				<div className="table-wrap rounded-2xl shadow-saas">
					<table className="data-table">
						<thead>
							<tr>
								<th>ID</th>
								<th>Title</th>
								<th>Customer</th>
								<th>Status</th>
								<th>Assignees</th>
								<th>Due</th>
								<th>Aging</th>
								<th>Delay owner</th>
								<th>Ticket</th>
							</tr>
						</thead>
						<tbody>
							{filtered.map((r) => (
								<tr key={String(r.name)}>
									<td>
										<Link to={portalTaskPath(String(r.name))} className="id-link">
											{r.name as string}
										</Link>
									</td>
									<td>{(r.subject as string) || "—"}</td>
									<td className="muted">{String(r.customer ?? "—")}</td>
									<td>
										<span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${statusBadgeClasses(String(r.status ?? ""))}`}>
											{String(r.status ?? "")}
										</span>
									</td>
									<td className="muted">{formatPortalAssignees(r)}</td>
									<td className="muted">{String(r.due_date ?? "").slice(0, 16) || "—"}</td>
									<td className="muted">{ageDays(r.creation, r.due_date, String(r.status ?? ""))}</td>
									<td className="muted">{String(r.delay_owner ?? "—")}</td>
									<td>
										{r.support_ticket ? (
											<Link to={portalTicketPath(String(r.support_ticket))} className="id-link">
												{String(r.support_ticket)}
											</Link>
										) : r.division ? (
											<span className="text-slate-600" title="Internal task (no ticket)">
												Internal · {String(r.division)}
											</span>
										) : (
											"—"
										)}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			) : (
				<div className="flex gap-3 overflow-x-auto pb-2">
					{[...KANBAN_ORDER, "Other"].map((col) => (
						<div key={col} className="min-w-[220px] max-w-[280px] flex-1 rounded-2xl border border-slate-200 bg-slate-50/80 p-3">
							<h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-600">
								{col} ({kanbanGrouped.get(col)?.length ?? 0})
							</h3>
							<ul className="flex flex-col gap-2">
								{(kanbanGrouped.get(col) ?? []).map((r) => (
									<li key={String(r.name)} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
										<Link to={portalTaskPath(String(r.name))} className="font-semibold text-indigo-700 hover:underline">
											{String(r.name)}
										</Link>
										<p className="mt-1 line-clamp-2 text-sm text-slate-700">{String(r.subject ?? "")}</p>
										<p className="mt-2 text-xs text-slate-500">{String(r.customer ?? "")}</p>
									</li>
								))}
							</ul>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
