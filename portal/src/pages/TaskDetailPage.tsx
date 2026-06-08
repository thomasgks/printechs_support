import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import CommunicationPanel from "../components/CommunicationPanel";
import FilesPanel from "../components/FilesPanel";
import HistorySummaryPanel from "../components/HistorySummaryPanel";
import StatusSelect from "../components/StatusSelect";
import TaskProgressStepper from "../components/TaskProgressStepper";
import TechnicianTaskAssignment from "../components/TechnicianTaskAssignment";
import {
	getPortalAssignmentUsers,
	getPortalBootstrap,
	getPortalTask,
	getPortalTaskStatusOptions,
	updatePortalTaskDueDate,
	updatePortalTaskStatus,
	portalTicketPath,
	type PortalAssignmentUserRow,
	type PortalBootstrapResult,
} from "../api";
import { formatPortalAssignees } from "../lib/assignees";
import { mergeStatusOptions, statusBadgeClasses } from "../lib/status";

function Row({ label, value }: { label: string; value: string | null | undefined }) {
	return (
		<div className="detail-row">
			<dt className="detail-dt">{label}</dt>
			<dd className="detail-dd">{value && String(value).trim() !== "" ? String(value) : "—"}</dd>
		</div>
	);
}

function fmtPortalDateTime(v: unknown): string | null {
	if (v == null || v === "") return null;
	const s = String(v).trim();
	return s !== "" ? s : null;
}

function dueCountdown(due: string | null): string | null {
	if (!due) return null;
	const t = new Date(due);
	if (Number.isNaN(t.getTime())) return null;
	const diff = t.getTime() - Date.now();
	const h = Math.round(diff / 3600000);
	if (diff < 0) return `${Math.abs(h)}h overdue`;
	return `${h}h remaining`;
}

function agingDays(creation: string | null): string | null {
	if (!creation) return null;
	const t = new Date(creation);
	if (Number.isNaN(t.getTime())) return null;
	const days = Math.floor((Date.now() - t.getTime()) / 86400000);
	return `${days}d`;
}

/** Coerce API flags; Frappe/JSON layers sometimes send 1/0 instead of booleans. */
function portalBoolOrNull(v: unknown): boolean | null {
	if (v === true || v === 1 || v === "1" || v === "true") return true;
	if (v === false || v === 0 || v === "0" || v === "false") return false;
	return null;
}

/** Map Frappe datetime string to `datetime-local` value. */
function frappeDatetimeToDatetimeLocal(v: unknown): string {
	const s = fmtPortalDateTime(v);
	if (!s) return "";
	const clean = s.replace(/\.\d+$/, "").trim();
	if (clean.length < 16) return "";
	return `${clean.slice(0, 10)}T${clean.slice(11, 16)}`;
}

function datetimeLocalToFrappePayload(v: string): string | null {
	const t = v.trim();
	if (!t) return null;
	if (t.includes("T")) {
		const [d, time] = t.split("T");
		const hm = (time || "00:00").slice(0, 5);
		return `${d} ${hm}:00`;
	}
	return t;
}

export default function TaskDetailPage() {
	const { taskId } = useParams();
	const location = useLocation();
	const name = taskId ? decodeURIComponent(taskId) : "";
	const [routeFlash] = useState<string | null>(() => {
		const st = location.state as { flashError?: string } | undefined;
		return st?.flashError ?? null;
	});
	const [doc, setDoc] = useState<Record<string, unknown> | null>(null);
	const [statusOptions, setStatusOptions] = useState<string[]>([]);
	const [bootstrap, setBootstrap] = useState<PortalBootstrapResult | null>(null);
	const [assignUsers, setAssignUsers] = useState<PortalAssignmentUserRow[]>([]);
	const [err, setErr] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [dueEdit, setDueEdit] = useState("");
	const [dueSaving, setDueSaving] = useState(false);
	const [dueErr, setDueErr] = useState<string | null>(null);

	useEffect(() => {
		if (!name) {
			setErr("Missing task");
			setLoading(false);
			return;
		}
		let c = false;
		(async () => {
			try {
				const [d, so, b] = await Promise.all([
					getPortalTask(name),
					getPortalTaskStatusOptions(),
					getPortalBootstrap(),
				]);
				if (!c) {
					setDoc(d);
					setDueEdit(frappeDatetimeToDatetimeLocal(d.due_date));
					setStatusOptions(so.options ?? []);
					setBootstrap(b);
					if (b.logged_in && "internal" in b && b.internal) {
						const u = await getPortalAssignmentUsers();
						if (!c) {
							setAssignUsers(u.users);
						}
					}
				}
			} catch (e) {
				if (!c) {
					setErr(e instanceof Error ? e.message : "Could not load task");
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
	}, [name]);

	const slaHint = useMemo(() => dueCountdown(fmtPortalDateTime(doc?.due_date)), [doc?.due_date]);

	if (loading) {
		return <p className="muted">Loading task…</p>;
	}
	if (err || !doc) {
		return (
			<div className="center-stage">
				<div className="card login-card">
					<p className="error-text">{err ?? "Not found"}</p>
					<p className="muted small">
						<Link to="/tasks">Back to tasks</Link>
					</p>
				</div>
			</div>
		);
	}

	const ticket = String(doc.support_ticket ?? "");
	const desc = String(doc.description ?? "");
	const status = String(doc.status ?? "");
	const internal =
		bootstrap && bootstrap.logged_in && "internal" in bootstrap
			? portalBoolOrNull(bootstrap.internal) ?? false
			: false;
	/** Server-driven; falls back to internal if older benches omit the flag. */
	const canEditDue =
		portalBoolOrNull(doc.can_edit_task_schedule) ?? internal;
	const au = doc.assigned_users;
	const assigneesList = Array.isArray(au) ? (au as unknown[]).map((x) => String(x)) : [];
	const stBadge = statusBadgeClasses(status);

	return (
		<div className="page-grid mx-auto w-full max-w-screen-2xl gap-8">
			<p className="detail-back">
				<Link to="/tasks" className="btn-text">
					← Tasks
				</Link>
			</p>
			{routeFlash ? (
				<div className="rounded-xl border border-amber-200/90 bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-sm">
					{routeFlash}
				</div>
			) : null}

			<section className="relative overflow-hidden rounded-3xl border border-slate-200/90 bg-gradient-to-br from-white via-indigo-50/40 to-violet-50/50 p-8 shadow-[0_24px_60px_-20px_rgba(79,70,229,0.22)]">
				<div className="pointer-events-none absolute -left-16 top-0 h-56 w-56 rounded-full bg-indigo-400/15 blur-3xl" />
				<div className="relative">
					<p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Support task</p>
					<h1 className="mt-2 font-['Syne',system-ui,sans-serif] text-3xl font-extrabold tracking-tight text-slate-900">
						{String(doc.subject ?? doc.name ?? "Task")}
					</h1>
					<p className="mt-2 font-mono text-sm text-slate-500">{String(doc.name)}</p>
					<div className="mt-4 flex flex-wrap items-center gap-2">
						<span className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ring-1 ${stBadge}`}>{status}</span>
						<span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-800 ring-1 ring-slate-200">
							{String(doc.task_type ?? "—")}
						</span>
					</div>
					<div className="mt-6">
						<TaskProgressStepper status={status} embedded />
					</div>
					<div className="mt-6 grid gap-4 border-t border-white/50 pt-6 sm:grid-cols-2 lg:grid-cols-4">
						<div>
							<p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Customer</p>
							<p className="font-medium text-slate-900">{String(doc.customer ?? "—")}</p>
						</div>
						<div>
							<p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assignees</p>
							<p className="font-medium text-slate-900">{formatPortalAssignees(doc)}</p>
						</div>
						<div className="min-w-0">
							<p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Due</p>
							{canEditDue ? (
								<div className="mt-1 space-y-2">
									<input
										type="datetime-local"
										className="w-full max-w-[14rem] rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 shadow-sm"
										value={dueEdit}
										onChange={(e) => {
											setDueEdit(e.target.value);
											setDueErr(null);
										}}
										disabled={dueSaving}
									/>
									<div className="flex flex-wrap items-center gap-2">
										<button
											type="button"
											className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
											disabled={dueSaving}
											onClick={async () => {
												setDueSaving(true);
												setDueErr(null);
												try {
													const payload = datetimeLocalToFrappePayload(dueEdit);
													await updatePortalTaskDueDate(String(doc.name), payload);
													const fresh = await getPortalTask(String(doc.name));
													setDoc(fresh as Record<string, unknown>);
													setDueEdit(frappeDatetimeToDatetimeLocal(fresh.due_date));
												} catch (e) {
													setDueErr(e instanceof Error ? e.message : "Could not save due date");
												} finally {
													setDueSaving(false);
												}
											}}
										>
											{dueSaving ? "Saving…" : "Save due date"}
										</button>
										<button
											type="button"
											className="text-xs font-semibold text-slate-600 underline underline-offset-2 disabled:opacity-50"
											disabled={dueSaving}
											onClick={async () => {
												setDueSaving(true);
												setDueErr(null);
												try {
													await updatePortalTaskDueDate(String(doc.name), null);
													const fresh = await getPortalTask(String(doc.name));
													setDoc(fresh as Record<string, unknown>);
													setDueEdit("");
												} catch (e) {
													setDueErr(e instanceof Error ? e.message : "Could not clear due date");
												} finally {
													setDueSaving(false);
												}
											}}
										>
											Clear
										</button>
									</div>
									{dueErr ? <p className="text-xs text-red-600">{dueErr}</p> : null}
								</div>
							) : (
								<p className="font-medium text-slate-900">{fmtPortalDateTime(doc.due_date) ?? "—"}</p>
							)}
						</div>
						<div>
							<p className="text-xs font-semibold uppercase tracking-wide text-slate-500">SLA clock</p>
							<p className={`font-semibold ${slaHint?.includes("overdue") ? "text-red-600" : "text-violet-700"}`}>
								{slaHint ?? "—"}
							</p>
						</div>
					</div>
					<div className="mt-6 rounded-2xl border border-white/60 bg-white/75 p-4 backdrop-blur">
						<StatusSelect
							label="Task status"
							value={status}
							options={mergeStatusOptions(status, statusOptions)}
							onSave={async (next) => {
								const r = await updatePortalTaskStatus(String(doc.name), next);
								setDoc((d) => (d ? { ...d, status: r.status } : d));
							}}
						/>
					</div>
				</div>
			</section>

			{internal ? (
				<TechnicianTaskAssignment
					taskName={String(doc.name)}
					initialAssignees={assigneesList}
					users={assignUsers}
					onUpdated={(patch) => setDoc((prev) => (prev ? { ...prev, ...patch } : prev))}
				/>
			) : null}

			<section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-saas">
				<h2 className="mb-4 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Task details</h2>
				<dl className="detail-dl">
					{ticket ? (
						<div className="detail-row">
							<dt className="detail-dt">Ticket</dt>
							<dd className="detail-dd">
								<Link to={portalTicketPath(ticket)} className="id-link">
									{ticket}
								</Link>
							</dd>
						</div>
					) : (
						<Row label="Ticket" value="" />
					)}
					<Row label="Division" value={String(doc.division ?? "")} />
					<Row label="Project" value={String(doc.project ?? "")} />
					<Row label="Responsible side" value={String(doc.responsible_side ?? "")} />
					<Row label="Parent / predecessor" value={String(doc.predecessor_task ?? "")} />
					<Row label="Aging (since creation)" value={agingDays(fmtPortalDateTime(doc.creation))} />
					<Row label="Planned start" value={fmtPortalDateTime(doc.planned_start_date)} />
					<Row label="Planned end" value={fmtPortalDateTime(doc.planned_end_date)} />
					<Row label="Actual start" value={fmtPortalDateTime(doc.actual_start_date)} />
					<Row label="Actual end" value={fmtPortalDateTime(doc.actual_end_date)} />
					<Row label="Updated" value={fmtPortalDateTime(doc.modified)} />
				</dl>
				{desc ? (
					<div className="detail-body">
						<h3 className="detail-body-title">Description</h3>
						<div className="detail-prose">{desc}</div>
					</div>
				) : null}
			</section>

			<section className="rounded-3xl border border-slate-200 bg-slate-50/50 p-6 shadow-saas">
				<h2 className="mb-2 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">SLA tracking</h2>
				<p className="mb-4 text-sm text-slate-600">
					First response and resolution targets are driven from the linked ticket. Internal users can open the ticket in this portal to
					review SLA fields; full configuration remains in ERPNext.
				</p>
				<div className="grid gap-3 sm:grid-cols-2">
					<div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
						Response SLA — see linked ticket (portal or Desk)
					</div>
					<div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
						Resolution SLA — see linked ticket (portal or Desk)
					</div>
				</div>
			</section>

			<section className="rounded-3xl border border-amber-200/80 bg-gradient-to-br from-amber-50/90 to-orange-50/40 p-6 shadow-saas">
				<h2 className="mb-4 font-['Syne',system-ui,sans-serif] text-lg font-bold text-amber-950">Delay accountability</h2>
				<dl className="detail-dl">
					<Row label="Delayed" value={Number(doc.is_delayed) ? "Yes" : "No"} />
					<Row label="Delay owner" value={String(doc.delay_owner ?? "")} />
					<Row label="Delay reason" value={String(doc.delay_reason ?? "")} />
					<Row label="Delay days" value={doc.delay_days != null ? String(doc.delay_days) : ""} />
					<Row label="Remarks" value={String(doc.delay_remarks ?? "")} />
				</dl>
			</section>

			{ticket ? (
				<div className="rounded-2xl border border-violet-100 bg-violet-50/40 px-4 py-3 text-center text-sm text-violet-900">
					<strong>Ticket-wide thread</strong> for the overall case:{" "}
					<Link to={portalTicketPath(ticket)} className="font-bold underline underline-offset-2">
						{ticket}
					</Link>
					. Messages below are <strong>task-specific</strong> and stay on this task.
				</div>
			) : null}
			<HistorySummaryPanel mode="task" name={String(doc.name)} doc={doc} />
			<CommunicationPanel
				taskName={String(doc.name)}
				communicationLocked={portalBoolOrNull(doc.communication_locked) ?? false}
				subtitle="Task-specific discussion. Internal notes stay hidden from customers when this task is linked to a ticket."
			/>
			{ticket ? <FilesPanel mode="ticket" name={ticket} title="Files on ticket" /> : null}

			<FilesPanel mode="task" name={String(doc.name)} title="Files on this task" />

			<section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-saas">
				<h2 className="mb-2 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Activity</h2>
				<p className="text-sm text-slate-600">
					Status changes may appear as system lines in the task or ticket threads above. File uploads are listed in the attachment panels. Full
					audit history is available in ERPNext Desk for users with desk access.
				</p>
			</section>
		</div>
	);
}
