import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Legend,
	Line,
	LineChart,
	Pie,
	PieChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import { getPortalDashboardStats, getPortalTasks, type PortalDashboardStats, portalTaskPath } from "../api";
import { statusBadgeClasses } from "../lib/status";

const COLORS = ["#64748b", "#2563eb", "#4f46e5", "#d97706", "#9333ea", "#16a34a", "#dc2626"];

function defaultStats(): PortalDashboardStats {
	return {
		pending_tickets: 0,
		overdue_tickets: 0,
		tickets_waiting_customer: 0,
		tickets_waiting_internal: 0,
		pending_tasks: 0,
		overdue_tasks: 0,
		completed_today: 0,
		waiting_customer: 0,
		waiting_internal: 0,
		sla_breached: 0,
		delayed_flagged: 0,
		tickets_by_status: {},
		tasks_by_status: {},
		assignee_load: [],
		monthly_completion: [],
	};
}

function mergeStats(raw: Partial<PortalDashboardStats> | null): PortalDashboardStats {
	const d = defaultStats();
	if (!raw) return d;
	return {
		...d,
		...raw,
		tickets_by_status: raw.tickets_by_status ?? {},
		tasks_by_status: raw.tasks_by_status ?? {},
		assignee_load: raw.assignee_load ?? [],
		monthly_completion: raw.monthly_completion ?? [],
	};
}

function KpiCard({
	label,
	value,
	hint,
	alert,
	to,
}: {
	label: string;
	value: number | string;
	hint?: string;
	alert?: boolean;
	to?: string;
}) {
	const inner = (
		<>
			<p className="dashboard-stat-label">{label}</p>
			<p className={`dashboard-stat-value ${alert ? "dashboard-stat-value--alert" : ""}`}>{value}</p>
			{hint ? <p className="dashboard-stat-hint muted small">{hint}</p> : null}
		</>
	);
	if (to) {
		return (
			<Link to={to} className={`dashboard-stat-card rounded-2xl shadow-saas ${alert ? "dashboard-stat-card--alert" : ""}`}>
				{inner}
			</Link>
		);
	}
	return (
		<div className={`dashboard-stat-card rounded-2xl shadow-saas ${alert ? "dashboard-stat-card--alert" : ""}`}>{inner}</div>
	);
}

export default function DashboardPage() {
	const [stats, setStats] = useState<PortalDashboardStats | null>(null);
	const [tasks, setTasks] = useState<Record<string, unknown>[]>([]);
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		let c = false;
		(async () => {
			try {
				const [s, t] = await Promise.all([getPortalDashboardStats(), getPortalTasks(80)]);
				if (!c) {
					setStats(mergeStats(s as Partial<PortalDashboardStats>));
					setTasks(t);
				}
			} catch (e) {
				if (!c) {
					setErr(e instanceof Error ? e.message : "Could not load stats");
				}
			}
		})();
		return () => {
			c = true;
		};
	}, []);

	const s = stats ?? defaultStats();

	const ticketDonutData = useMemo(() => {
		return Object.entries(s.tickets_by_status).map(([name, value]) => ({ name, value }));
	}, [s.tickets_by_status]);

	const taskDonutData = useMemo(() => {
		return Object.entries(s.tasks_by_status).map(([name, value]) => ({ name, value }));
	}, [s.tasks_by_status]);

	const lineData = s.monthly_completion;

	const barData = s.assignee_load.map((r) => ({ name: r.name.length > 18 ? `${r.name.slice(0, 16)}…` : r.name, tasks: r.count }));

	const now = new Date();
	const overdueRows = useMemo(() => {
		return tasks.filter((r) => {
			const st = String(r.status ?? "");
			if (st === "Completed" || st === "Cancelled") return false;
			const d = r.due_date;
			if (!d) return false;
			const t = new Date(String(d));
			return !Number.isNaN(t.getTime()) && t < now;
		});
	}, [tasks]);

	const todayStr = now.toISOString().slice(0, 10);
	const todayRows = useMemo(() => {
		return tasks.filter((r) => {
			const d = r.due_date;
			if (!d) return false;
			return String(d).slice(0, 10) === todayStr;
		});
	}, [tasks, todayStr]);

	return (
		<div className="page-grid">
			<section className="hero-card rounded-2xl shadow-saas-lg">
				<p className="eyebrow">Printechs Support</p>
				<h2 className="hero-title">Operations dashboard</h2>
				<p className="hero-lead">
					Support <strong>tickets</strong> (cases) and <strong>tasks</strong> (work lines). KPIs and charts are split so you
					can see both. Data respects your portal visibility (customer vs internal).
				</p>
			</section>

			{err ? <p className="error-text small">{err}</p> : null}

			<section className="space-y-2" aria-label="Ticket KPIs">
				<h3 className="font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Tickets</h3>
				<p className="text-xs text-slate-500">Case-level records (subject, customer, ticket status)</p>
				<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
					<KpiCard label="Open tickets" value={s.pending_tickets} hint="Not resolved / closed" to="/tickets" />
					<KpiCard
						label="Overdue tickets"
						value={s.overdue_tickets}
						hint="Past ticket due date"
						alert={s.overdue_tickets > 0}
						to="/tickets"
					/>
					<KpiCard
						label="Waiting on customer"
						value={s.tickets_waiting_customer}
						hint="Ticket status"
						to="/tickets"
					/>
					<KpiCard
						label="Waiting internal"
						value={s.tickets_waiting_internal}
						hint="Ticket status"
						to="/tickets"
					/>
				</div>
			</section>

			<section className="space-y-2" aria-label="Task KPIs">
				<h3 className="font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Tasks</h3>
				<p className="text-xs text-slate-500">Work items linked to tickets (scheduling & execution)</p>
				<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
					<KpiCard label="Open tasks" value={s.pending_tasks} hint="Not completed" to="/tasks" />
					<KpiCard label="Overdue tasks" value={s.overdue_tasks} hint="Due passed" alert={s.overdue_tasks > 0} to="/tasks" />
					<KpiCard label="Tasks done today" value={s.completed_today} hint="Completed (by modified)" to="/tasks" />
					<KpiCard label="SLA at risk" value={s.sla_breached} hint="Open tasks & past due" alert={s.sla_breached > 0} to="/tasks" />
					<KpiCard label="Tasks · waiting customer" value={s.waiting_customer} hint="Task status" to="/tasks" />
					<KpiCard label="Tasks · waiting Printechs" value={s.waiting_internal} hint="Task status" to="/tasks" />
				</div>
			</section>

			<section className="grid gap-4 lg:grid-cols-2">
				<div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-saas">
					<h3 className="mb-1 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Tickets by status</h3>
					<p className="mb-3 text-xs text-slate-500">Support Ticket records in your scope</p>
					<div className="h-56 w-full">
						{ticketDonutData.length ? (
							<ResponsiveContainer width="100%" height="100%">
								<PieChart>
									<Pie
										data={ticketDonutData}
										dataKey="value"
										nameKey="name"
										innerRadius={48}
										outerRadius={72}
										paddingAngle={2}
									>
										{ticketDonutData.map((_, i) => (
											<Cell key={i} fill={COLORS[i % COLORS.length]} />
										))}
									</Pie>
									<Tooltip />
									<Legend />
								</PieChart>
							</ResponsiveContainer>
						) : (
							<p className="muted flex h-full items-center justify-center text-sm">No ticket data</p>
						)}
					</div>
				</div>
				<div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-saas">
					<h3 className="mb-1 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Tasks by status</h3>
					<p className="mb-3 text-xs text-slate-500">Support Task lines in your scope</p>
					<div className="h-56 w-full">
						{taskDonutData.length ? (
							<ResponsiveContainer width="100%" height="100%">
								<PieChart>
									<Pie data={taskDonutData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={2}>
										{taskDonutData.map((_, i) => (
											<Cell key={i} fill={COLORS[i % COLORS.length]} />
										))}
									</Pie>
									<Tooltip />
									<Legend />
								</PieChart>
							</ResponsiveContainer>
						) : (
							<p className="muted flex h-full items-center justify-center text-sm">No task data</p>
						)}
					</div>
				</div>
			</section>

			<section className="grid gap-4 lg:grid-cols-1">
				<div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-saas">
					<h3 className="mb-1 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Monthly completions</h3>
					<p className="mb-3 text-xs text-slate-500">Completed tasks by calendar month (modified)</p>
					<div className="h-56 w-full">
						{lineData.some((x) => x.count > 0) ? (
							<ResponsiveContainer width="100%" height="100%">
								<LineChart data={lineData}>
									<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
									<XAxis dataKey="label" tick={{ fontSize: 11 }} />
									<YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
									<Tooltip />
									<Line type="monotone" dataKey="count" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
								</LineChart>
							</ResponsiveContainer>
						) : (
							<p className="muted flex h-full items-center justify-center text-sm">No completion trend yet</p>
						)}
					</div>
				</div>
			</section>

			<section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-saas">
				<h3 className="mb-1 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Engineer workload</h3>
				<p className="mb-3 text-xs text-slate-500">Open tasks by assignee</p>
				<div className="h-52 w-full">
					{barData.length ? (
						<ResponsiveContainer width="100%" height="100%">
							<BarChart data={barData} layout="vertical" margin={{ left: 8, right: 8 }}>
								<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
								<XAxis type="number" allowDecimals={false} />
								<YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
								<Tooltip />
								<Bar dataKey="tasks" fill="#6366f1" radius={[0, 6, 6, 0]} />
							</BarChart>
						</ResponsiveContainer>
					) : (
						<p className="muted flex h-full items-center justify-center text-sm">No assignee data</p>
					)}
				</div>
			</section>

			<div className="grid gap-4 lg:grid-cols-2">
				<section className="rounded-2xl border border-red-200 bg-red-50/40 p-4 shadow-saas">
					<h3 className="mb-3 font-['Syne',system-ui,sans-serif] text-lg font-bold text-red-800">Overdue tasks</h3>
					{overdueRows.length ? (
						<ul className="space-y-2">
							{overdueRows.slice(0, 8).map((r) => (
								<li key={String(r.name)} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white/90 px-3 py-2 text-sm shadow-sm">
									<Link to={portalTaskPath(String(r.name))} className="font-semibold text-indigo-700 hover:underline">
										{r.name as string}
									</Link>
									<span className="text-slate-600">{String(r.subject ?? "")}</span>
									<span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${statusBadgeClasses(String(r.status ?? ""))}`}>
										{String(r.status ?? "")}
									</span>
								</li>
							))}
						</ul>
					) : (
						<p className="text-sm text-slate-600">No overdue tasks in current list.</p>
					)}
				</section>
				<section className="rounded-2xl border border-violet-200 bg-violet-50/30 p-4 shadow-saas">
					<h3 className="mb-3 font-['Syne',system-ui,sans-serif] text-lg font-bold text-violet-900">Due today</h3>
					{todayRows.length ? (
						<ul className="space-y-2">
							{todayRows.slice(0, 8).map((r) => (
								<li key={String(r.name)} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white/90 px-3 py-2 text-sm shadow-sm">
									<Link to={portalTaskPath(String(r.name))} className="font-semibold text-indigo-700 hover:underline">
										{r.name as string}
									</Link>
									<span className="text-slate-600">{String(r.subject ?? "")}</span>
								</li>
							))}
						</ul>
					) : (
						<p className="text-sm text-slate-600">No tasks due today in the loaded list.</p>
					)}
				</section>
			</div>

			<section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-saas">
				<h3 className="mb-2 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Recent activity</h3>
				<p className="mb-3 text-sm text-slate-500">
					Full audit trail will appear when comment & timeline APIs are wired. For now, use task detail in Desk for history.
				</p>
				<div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-4 py-6 text-center text-sm text-slate-500">
					Activity feed — planned (comments, status changes, files).
				</div>
			</section>
		</div>
	);
}
