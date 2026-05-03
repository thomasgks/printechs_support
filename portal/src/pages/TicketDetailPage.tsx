import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import CommunicationPanel from "../components/CommunicationPanel";
import FilesPanel from "../components/FilesPanel";
import StatusSelect from "../components/StatusSelect";
import {
	getPortalAssignmentUsers,
	getPortalBootstrap,
	getPortalTeams,
	getPortalTicket,
	getPortalTicketStatusOptions,
	getPortalTasksForTicket,
	markTicketAwaitingCustomerResolution,
	updatePortalTicketDueDate,
	updatePortalTicketStatus,
	type PortalAssignmentUserRow,
	type PortalBootstrapResult,
	type PortalTeamRow,
	portalTaskNewPath,
	portalTaskPath,
} from "../api";
import TechnicianTicketAssignment from "../components/TechnicianTicketAssignment";
import { formatPortalAssignees } from "../lib/assignees";
import { mergeStatusOptions, statusBadgeClasses } from "../lib/status";
import { rewriteDeskHtmlLinks } from "../lib/deskLinks";

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

function portalBoolOrNull(v: unknown): boolean | null {
	if (v === true || v === 1 || v === "1" || v === "true") return true;
	if (v === false || v === 0 || v === "0" || v === "false") return false;
	return null;
}

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

export default function TicketDetailPage() {
	const { ticketId } = useParams();
	const name = ticketId ? decodeURIComponent(ticketId) : "";
	const [doc, setDoc] = useState<Record<string, unknown> | null>(null);
	const [statusOptions, setStatusOptions] = useState<string[]>([]);
	const [bootstrap, setBootstrap] = useState<PortalBootstrapResult | null>(null);
	const [teams, setTeams] = useState<PortalTeamRow[]>([]);
	const [assignUsers, setAssignUsers] = useState<PortalAssignmentUserRow[]>([]);
	const [err, setErr] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [confirmationBusy, setConfirmationBusy] = useState(false);
	const [dueEdit, setDueEdit] = useState("");
	const [dueSaving, setDueSaving] = useState(false);
	const [dueErr, setDueErr] = useState<string | null>(null);
	const [linkedTasks, setLinkedTasks] = useState<Record<string, unknown>[]>([]);
	const [linkedTasksLoading, setLinkedTasksLoading] = useState(true);

	useEffect(() => {
		if (!name) {
			setErr("Missing ticket");
			setLoading(false);
			return;
		}
		let c = false;
		(async () => {
			try {
				const [d, so, b] = await Promise.all([
					getPortalTicket(name),
					getPortalTicketStatusOptions(name),
					getPortalBootstrap(),
				]);
				if (!c) {
					setDoc(d);
					setDueEdit(frappeDatetimeToDatetimeLocal(d.due_date));
					setStatusOptions(so.options ?? []);
					setBootstrap(b);
					if (b.logged_in && "internal" in b && b.internal) {
						const [t, u] = await Promise.all([getPortalTeams(), getPortalAssignmentUsers()]);
						if (!c) {
							setTeams(t.teams);
							setAssignUsers(u.users);
						}
					}
				}
			} catch (e) {
				if (!c) {
					setErr(e instanceof Error ? e.message : "Could not load ticket");
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

	useEffect(() => {
		if (!name) return;
		let c = false;
		setLinkedTasksLoading(true);
		(async () => {
			try {
				const rows = await getPortalTasksForTicket(name, 100);
				if (!c) setLinkedTasks(rows);
			} catch {
				if (!c) setLinkedTasks([]);
			} finally {
				if (!c) setLinkedTasksLoading(false);
			}
		})();
		return () => {
			c = true;
		};
	}, [name]);

	if (loading) {
		return <p className="muted">Loading ticket…</p>;
	}
	if (err || !doc) {
		return (
			<div className="center-stage">
				<div className="card login-card">
					<p className="error-text">{err ?? "Not found"}</p>
					<p className="muted small">
						<Link to="/tickets">Back to tickets</Link>
					</p>
				</div>
			</div>
		);
	}

	const desc = String(doc.description ?? "");
	const status = String(doc.status ?? "");
	const terminalStatuses = new Set(["Resolved", "Closed", "Cancelled"]);
	const communicationLocked =
		portalBoolOrNull(doc.communication_locked) === true || terminalStatuses.has(status);
	const resolutionDeadline = doc.customer_resolution_deadline;
	const deadlineStr =
		resolutionDeadline != null && String(resolutionDeadline).trim() !== ""
			? fmtPortalDateTime(resolutionDeadline)
			: null;
	const internal =
		bootstrap && bootstrap.logged_in && "internal" in bootstrap
			? portalBoolOrNull(bootstrap.internal) ?? false
			: false;
	/** Only when API exposes the flag (avoids calling missing RPC on older benches). */
	const canEditTicketDue = portalBoolOrNull(doc.can_edit_ticket_schedule) === true;
	/** Match server: only after work is done and the ticket is waiting on the customer. */
	const canRequestCustomerConfirmation =
		internal && !terminalStatuses.has(status) && status === "Waiting for Customer";
	/** API returns `["Resolved"]` only while the technician confirmation window is open. */
	const customerCanConfirmResolved =
		!internal && !terminalStatuses.has(status) && statusOptions.includes("Resolved");
	const assigneesRaw = doc.assigned_users;
	const assigneesList = Array.isArray(assigneesRaw)
		? (assigneesRaw as unknown[]).map((x) => String(x))
		: [];

	return (
		<div className="page-grid mx-auto w-full max-w-screen-2xl gap-8">
			<p className="detail-back">
				<Link to="/tickets" className="btn-text">
					← Tickets
				</Link>
			</p>

			<section className="relative overflow-hidden rounded-3xl border border-slate-200/90 bg-gradient-to-br from-white via-violet-50/30 to-indigo-50/40 p-8 shadow-[0_24px_60px_-20px_rgba(79,70,229,0.25)]">
				<div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-violet-400/20 blur-3xl" />
				<div className="relative">
					<p className="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">Support ticket</p>
					<h1 className="mt-2 font-['Syne',system-ui,sans-serif] text-3xl font-extrabold tracking-tight text-slate-900">
						{String(doc.subject ?? doc.name ?? "Ticket")}
					</h1>
					<div className="mt-2 flex flex-wrap items-center gap-3">
						<p className="font-mono text-sm text-slate-500">{String(doc.name)}</p>
						{internal ? (
							<Link
								to={portalTaskNewPath(String(doc.name))}
								className="text-sm font-semibold text-indigo-700 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-900"
							>
								+ New task
							</Link>
						) : null}
					</div>
					<div className="mt-4 flex flex-wrap items-center gap-2">
						<span className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ring-1 ${statusBadgeClasses(status)}`}>
							{status}
						</span>
						<span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
							{String(doc.priority ?? "—")}
						</span>
					</div>
					<div className="mt-6 rounded-2xl border border-white/60 bg-white/70 p-4 backdrop-blur">
						{!internal && deadlineStr && !terminalStatuses.has(status) ? (
							<div className="mb-4 rounded-xl border border-amber-200/90 bg-amber-50/95 px-4 py-3 text-sm text-amber-950 shadow-sm">
								<strong>Confirmation requested.</strong> If your issue is fixed, set status to{" "}
								<strong>Resolved</strong>. Respond by {deadlineStr} or the ticket will be marked Resolved
								automatically.
							</div>
						) : null}
						{internal ? (
							<StatusSelect
								label="Update status"
								value={status}
								options={mergeStatusOptions(status, statusOptions)}
								onSave={async (next) => {
									const r = await updatePortalTicketStatus(String(doc.name), next);
									setDoc((d) => (d ? { ...d, status: r.status } : d));
									const so = await getPortalTicketStatusOptions(String(doc.name));
									setStatusOptions(so.options ?? []);
								}}
							/>
						) : customerCanConfirmResolved ? (
							<StatusSelect
								label="Confirm resolution"
								value={status}
								options={mergeStatusOptions(status, statusOptions)}
								onSave={async (next) => {
									const r = await updatePortalTicketStatus(String(doc.name), next);
									setDoc((d) =>
										d
											? {
													...d,
													status: r.status,
													...(next === "Resolved"
														? {
																customer_resolution_deadline: null,
																customer_confirmation_required: 0,
															}
														: {}),
												}
											: d,
									);
									const so = await getPortalTicketStatusOptions(String(doc.name));
									setStatusOptions(so.options ?? []);
								}}
							/>
						) : (
							<div className="rounded-xl border border-slate-200/80 bg-slate-50/90 px-4 py-3 text-sm text-slate-700">
								{terminalStatuses.has(status) ? (
									<p>
										This ticket is closed. If you need anything else, reply in the thread below or contact
										your support team.
									</p>
								) : (
									<p>
										Ticket status is managed by your support team. When they finish work, you may be asked to
										confirm resolution here.
									</p>
								)}
							</div>
						)}
						{canRequestCustomerConfirmation ? (
							<div className="mt-4">
								<button
									type="button"
									className="rounded-xl border border-violet-400/80 bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-60"
									disabled={confirmationBusy}
									onClick={async () => {
										setConfirmationBusy(true);
										try {
											const r = await markTicketAwaitingCustomerResolution(String(doc.name), 24);
											setDoc((prev) =>
												prev
													? {
															...prev,
															customer_resolution_deadline: r.customer_resolution_deadline,
															customer_confirmation_required: 1,
														}
													: prev,
											);
											const so = await getPortalTicketStatusOptions(String(doc.name));
											setStatusOptions(so.options ?? []);
										} finally {
											setConfirmationBusy(false);
										}
									}}
								>
									{confirmationBusy ? "Opening…" : "Request customer confirmation (24h)"}
								</button>
								<p className="mt-2 text-xs text-slate-600">
									Opens a portal window for the customer to confirm Resolved; auto-resolves after the deadline if
									they do not respond.
								</p>
							</div>
						) : null}
						{internal && !terminalStatuses.has(status) && !canRequestCustomerConfirmation ? (
							<p className="mt-4 text-xs text-slate-600">
								When your work is complete, set status to <strong>Waiting for Customer</strong>, then you can
								request confirmation for the customer to resolve the ticket in the portal.
							</p>
						) : null}
					</div>
				</div>
			</section>

			<section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-saas">
				<h2 className="mb-4 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Details</h2>
				<dl className="detail-dl">
					<Row label="Customer" value={String(doc.customer_name || doc.customer || "")} />
					<Row label="Ticket type" value={String(doc.ticket_type_label || doc.ticket_type || "")} />
					<Row label="Team" value={String(doc.team ?? "")} />
					<Row label="Division" value={String(doc.division ?? "")} />
					<Row label="Assignees" value={formatPortalAssignees(doc)} />
					<Row label="Opening" value={fmtPortalDateTime(doc.opening_date)} />
					<div className="detail-row">
						<dt className="detail-dt">Due</dt>
						<dd className="detail-dd">
							{canEditTicketDue ? (
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
													await updatePortalTicketDueDate(String(doc.name), payload);
													const fresh = await getPortalTicket(String(doc.name));
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
													await updatePortalTicketDueDate(String(doc.name), null);
													const fresh = await getPortalTicket(String(doc.name));
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
									<p className="text-xs text-slate-500">
										Applies to this ticket and all non-cancelled tasks. Optional at assignment.
									</p>
								</div>
							) : (
								fmtPortalDateTime(doc.due_date) ?? "—"
							)}
						</dd>
					</div>
					<Row label="Updated" value={fmtPortalDateTime(doc.modified)} />
				</dl>
				{desc ? (
					<div className="detail-body">
						<h3 className="detail-body-title">Description</h3>
						<div className="detail-prose">{desc}</div>
					</div>
				) : null}
			</section>

			<section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-saas">
				<div className="mb-4 flex flex-wrap items-center justify-between gap-3">
					<h2 className="font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Tasks for this ticket</h2>
					{internal ? (
						<Link
							to={portalTaskNewPath(String(doc.name))}
							className="text-sm font-semibold text-indigo-700 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-900"
						>
							+ New task
						</Link>
					) : null}
				</div>
				{linkedTasksLoading ? (
					<p className="muted text-sm">Loading tasks…</p>
				) : linkedTasks.length === 0 ? (
					<p className="text-sm text-slate-600">
						No support tasks linked yet.
						{internal ? (
							<>
								{" "}
								<Link to={portalTaskNewPath(String(doc.name))} className="font-semibold text-indigo-700 hover:underline">
									Create one
								</Link>{" "}
								— it will appear here for everyone with access to this ticket.
							</>
						) : null}
					</p>
				) : (
					<ul className="divide-y divide-slate-100 rounded-xl border border-slate-100">
						{linkedTasks.map((t) => (
							<li key={String(t.name)} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
								<div>
									<Link
										to={portalTaskPath(String(t.name))}
										className="font-mono font-semibold text-indigo-700 hover:underline"
									>
										{String(t.name)}
									</Link>
									<span className="mx-2 text-slate-300">·</span>
									<span className="text-slate-800">{String(t.subject ?? "")}</span>
								</div>
								<div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
									<span
										className={`inline-flex rounded-full px-2 py-0.5 font-semibold ring-1 ${statusBadgeClasses(String(t.status ?? ""))}`}
									>
										{String(t.status ?? "")}
									</span>
									{fmtPortalDateTime(t.due_date) ? <span>Due {fmtPortalDateTime(t.due_date)}</span> : null}
								</div>
							</li>
						))}
					</ul>
				)}
			</section>

			{internal ? (
				<TechnicianTicketAssignment
					ticketName={String(doc.name)}
					initialTeam={String(doc.team ?? "")}
					initialAssignees={assigneesList}
					teams={teams}
					users={assignUsers}
					onUpdated={(patch) => {
						setDoc((prev) => (prev ? { ...prev, ...patch } : prev));
					}}
				/>
			) : null}

			{(() => {
				const resHtml = String(doc.resolution_summary_html ?? "").trim();
				const resType = String(doc.resolution_type ?? "").trim();
				const ro = fmtPortalDateTime(doc.resolved_on);
				const co = fmtPortalDateTime(doc.closed_on);
				const rootCause = internal ? String(doc.root_cause ?? "").trim() : "";
				const showResolutionCard =
					terminalStatuses.has(status) || Boolean(resHtml || resType || ro || co || rootCause);
				if (!showResolutionCard) {
					return null;
				}
				return (
					<section className="rounded-3xl border border-emerald-200/90 bg-gradient-to-br from-emerald-50/80 via-white to-slate-50/90 p-6 shadow-[0_12px_40px_-12px_rgba(15,23,42,0.1)]">
						<h2 className="mb-3 font-['Syne',system-ui,sans-serif] text-lg font-bold text-slate-900">Resolution</h2>
						<p className="mb-4 text-xs text-slate-500">
							Official closure summary and timestamps. The conversation thread below is read-only when the ticket is resolved or closed.
						</p>
						<dl className="detail-dl mb-4">
							{ro ? <Row label="Resolved on" value={ro} /> : null}
							{co ? <Row label="Closed on" value={co} /> : null}
							{resType ? <Row label="Resolution type" value={resType} /> : null}
						</dl>
						{rootCause ? (
							<div className="mb-4 rounded-2xl border border-slate-200 bg-white/90 px-4 py-3">
								<p className="text-[0.65rem] font-bold uppercase tracking-wide text-slate-500">Root cause (internal)</p>
								<p className="mt-1 text-sm text-slate-800">{rootCause}</p>
							</div>
						) : null}
						{resHtml ? (
							<div
								className="detail-prose portal-thread-html max-w-none rounded-2xl border border-emerald-100 bg-white/90 px-4 py-3 text-sm text-slate-800"
								dangerouslySetInnerHTML={{ __html: rewriteDeskHtmlLinks(resHtml) }}
							/>
						) : (
							<p className="text-sm text-slate-500">No resolution summary recorded yet.</p>
						)}
					</section>
				);
			})()}

			<CommunicationPanel
				ticketName={String(doc.name)}
				ticketStatus={String(doc.status ?? "")}
				subtitle="All stakeholders on this ticket see customer-visible messages."
				communicationLocked={communicationLocked}
				onAfterMessageSent={async () => {
					const fresh = await getPortalTicket(String(doc.name));
					setDoc(fresh as Record<string, unknown>);
					setDueEdit(frappeDatetimeToDatetimeLocal(fresh.due_date));
					const so = await getPortalTicketStatusOptions(String(doc.name));
					setStatusOptions(so.options ?? []);
				}}
			/>

			<FilesPanel mode="ticket" name={String(doc.name)} uploadDisabled={communicationLocked} />
		</div>
	);
}
