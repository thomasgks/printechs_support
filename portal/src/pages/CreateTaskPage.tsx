import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
	createPortalSupportTask,
	getPortalAssignmentUsers,
	getPortalBootstrap,
	getPortalTicket,
	getPortalTickets,
	portalTaskPath,
	updatePortalTaskAssignment,
	type PortalAssignmentUserRow,
	type PortalBootstrapResult,
} from "../api";
import { portalAssignmentUserLabel } from "../lib/assignmentUsers";
function localDatetimeToFrappe(v: string): string | null {
	const t = v.trim();
	if (!t) return null;
	if (!t.includes("T")) return t;
	const [d, hhmm] = t.split("T");
	const hm = (hhmm || "00:00").slice(0, 5);
	return `${d} ${hm}:00`;
}

const TASK_TYPES = [
	"Internal Task",
	"Customer Action",
	"Follow-up",
	"Development",
	"Testing",
	"UAT",
	"Training",
	"Meeting",
	"Implementation Step",
] as const;

const DIVISIONS = ["Software", "Industrial", "Retail"] as const;

type ResponsibleSide = "Printechs" | "Customer";

export default function CreateTaskPage() {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const presetTicket = (searchParams.get("ticket") ?? "").trim();

	const [bootstrap, setBootstrap] = useState<Extract<PortalBootstrapResult, { logged_in: true }> | null>(null);
	const [tickets, setTickets] = useState<{ name: string; subject: string }[]>([]);
	const [standaloneInternal, setStandaloneInternal] = useState(false);
	const [supportTicket, setSupportTicket] = useState(presetTicket);
	const [division, setDivision] = useState<string>(DIVISIONS[0]);
	const [subject, setSubject] = useState("");
	const [description, setDescription] = useState("");
	const [taskType, setTaskType] = useState<string>(TASK_TYPES[0]);
	const [dueDate, setDueDate] = useState("");
	const [responsibleSide, setResponsibleSide] = useState<ResponsibleSide>("Printechs");
	const [ticketCustomer, setTicketCustomer] = useState("");
	const [ticketCustomerName, setTicketCustomerName] = useState("");
	/** Who works the task when responsibility is Printechs (applied after create). */
	const [assignUsers, setAssignUsers] = useState<PortalAssignmentUserRow[]>([]);
	const [assignPrimary, setAssignPrimary] = useState("");
	const [assignCo, setAssignCo] = useState<string[]>([]);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		let c = false;
		(async () => {
			try {
				const b = await getPortalBootstrap();
				if (!b.logged_in) {
					if (!c) setErr("Not signed in");
					return;
				}
				if (!c) setBootstrap(b);
				if (!b.internal) {
					if (!c) setErr("Only internal team members can create tasks from the portal.");
					return;
				}
				const list = await getPortalTickets(200, { activeOnly: true });
				if (!c) {
					const mapped = list.map((row) => ({
						name: String(row.name ?? ""),
						subject: String(row.subject ?? ""),
					}));
					let options = mapped;
					if (presetTicket && !mapped.some((t) => t.name === presetTicket)) {
						try {
							const doc = await getPortalTicket(presetTicket);
							if (!c) {
								options = [
									{
										name: presetTicket,
										subject: String(doc.subject ?? "").trim() || "(no subject)",
									},
									...mapped,
								];
							}
						} catch {
							if (!c) {
								setErr(
									`Ticket “${presetTicket}” was not found or you have no access. Choose another ticket or use Internal — no ticket.`,
								);
								setSupportTicket("");
							}
						}
					}
					setTickets(options);
					if (presetTicket && options.some((t) => t.name === presetTicket)) {
						setSupportTicket(presetTicket);
						setStandaloneInternal(false);
					}
				}
			} catch (e) {
				if (!c) {
					setErr(e instanceof Error ? e.message : "Could not load");
				}
			} finally {
				if (!c) setLoading(false);
			}
		})();
		return () => {
			c = true;
		};
	}, [presetTicket]);

	const [assignUsersLoading, setAssignUsersLoading] = useState(false);

	useEffect(() => {
		if (standaloneInternal || !supportTicket.trim()) {
			setTicketCustomer("");
			setTicketCustomerName("");
			return;
		}
		let c = false;
		(async () => {
			try {
				const doc = await getPortalTicket(supportTicket.trim());
				if (!c) {
					setTicketCustomer(String(doc.customer ?? "").trim());
					setTicketCustomerName(String(doc.customer_name ?? "").trim());
				}
			} catch {
				if (!c) {
					setTicketCustomer("");
					setTicketCustomerName("");
				}
			}
		})();
		return () => {
			c = true;
		};
	}, [standaloneInternal, supportTicket]);

	useEffect(() => {
		if (responsibleSide !== "Printechs") {
			setAssignPrimary("");
			setAssignCo([]);
			setAssignUsersLoading(false);
			return;
		}
		let c = false;
		setAssignUsersLoading(true);
		(async () => {
			try {
				const u = await getPortalAssignmentUsers();
				if (!c) setAssignUsers(u.users);
			} catch {
				if (!c) setAssignUsers([]);
			} finally {
				if (!c) setAssignUsersLoading(false);
			}
		})();
		return () => {
			c = true;
		};
	}, [responsibleSide]);

	function toggleCoAssignee(name: string) {
		if (name === assignPrimary) return;
		setAssignCo((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
	}

	const internal = Boolean(bootstrap?.internal);

	const onSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setErr(null);
		const tk = supportTicket.trim();
		const sub = subject.trim();
		if (!standaloneInternal && !tk) {
			setErr("Select a ticket, or choose an internal task without a ticket.");
			return;
		}
		if (standaloneInternal && !division) {
			setErr("Division is required for internal tasks without a ticket.");
			return;
		}
		if (!sub) {
			setErr("Task title is required");
			return;
		}
		if (responsibleSide === "Customer" && standaloneInternal) {
			setErr("Customer responsibility requires a linked support ticket.");
			return;
		}
		if (responsibleSide === "Customer" && !standaloneInternal && !ticketCustomer) {
			setErr("This ticket has no customer linked. Choose Printechs responsibility or pick another ticket.");
			return;
		}
		setSaving(true);
		try {
			const desc = description.trim();
			const base = {
				subject: sub,
				task_type: taskType,
				due_date: dueDate.trim() ? localDatetimeToFrappe(dueDate) : null,
				responsible_side: responsibleSide,
				...(desc ? { description: desc } : {}),
			};
			const res = await createPortalSupportTask(
				standaloneInternal
					? { ...base, division }
					: { ...base, support_ticket: tk },
			);
			if (responsibleSide === "Printechs") {
				const list = [assignPrimary.trim(), ...assignCo.filter((x) => x && x !== assignPrimary)].filter(Boolean);
				if (list.length) {
					try {
						await updatePortalTaskAssignment(res.name, JSON.stringify(list));
					} catch (e2) {
						navigate(portalTaskPath(res.name), {
							state: {
								flashError: `Assignees could not be saved: ${e2 instanceof Error ? e2.message : "Unknown error"}. Use the assignment panel on this page.`,
							},
						});
						return;
					}
				}
			}
			navigate(portalTaskPath(res.name));
		} catch (e) {
			setErr(e instanceof Error ? e.message : "Could not create task");
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return <p className="muted">Loading…</p>;
	}

	if (!internal) {
		return (
			<div className="page-grid max-w-2xl gap-6">
				<p className="error-text">Only internal team members can create support tasks from the portal.</p>
				<p className="muted text-sm">
					Create tasks from Desk, or ask an administrator to grant an internal role (e.g. Support Engineer).
				</p>
				<Link to="/tasks" className="btn-text">
					← Back to tasks
				</Link>
			</div>
		);
	}

	const ticketPickerDisabled = standaloneInternal;
	const canSubmit =
		standaloneInternal || (Boolean(supportTicket.trim()) && tickets.some((t) => t.name === supportTicket.trim()));

	return (
		<div className="page-grid max-w-2xl gap-6">
			<p className="detail-back">
				<Link to="/tasks" className="btn-text">
					← Tasks
				</Link>
			</p>
			<section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-saas">
				<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">New task</h1>
				<p className="mt-1 text-sm text-slate-600">
					For customer work, link a task to an <strong>open</strong> ticket (create the task from the ticket page when
					possible so the list stays obvious). For internal work, use <strong>Internal — no ticket</strong> and pick a
					division.
				</p>

				{err ? <p className="error-text mt-4 text-sm">{err}</p> : null}

				<form onSubmit={onSubmit} className="mt-6 space-y-4">
					<fieldset className="space-y-2 rounded-xl border border-slate-100 bg-slate-50/80 p-4">
						<legend className="px-1 text-xs font-bold uppercase tracking-wide text-slate-500">Scope</legend>
						<label className="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
							<input
								type="radio"
								name="scope"
								className="mt-1"
								checked={!standaloneInternal}
								onChange={() => setStandaloneInternal(false)}
							/>
							<span>
								<span className="font-semibold">Link to a support ticket</span>
								<span className="block text-slate-600">Only non-closed tickets are listed.</span>
							</span>
						</label>
						<label className="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
							<input
								type="radio"
								name="scope"
								className="mt-1"
								checked={standaloneInternal}
								onChange={() => {
									setStandaloneInternal(true);
									setSupportTicket("");
								}}
							/>
							<span>
								<span className="font-semibold">Internal — no ticket</span>
								<span className="block text-slate-600">For internal team work that does not need a customer ticket.</span>
							</span>
						</label>
					</fieldset>

					{standaloneInternal ? (
						<label className="flex flex-col gap-1 text-sm font-semibold text-slate-800">
							Division
							<select
								required
								className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-slate-900"
								value={division}
								onChange={(e) => setDivision(e.target.value)}
							>
								{DIVISIONS.map((d) => (
									<option key={d} value={d}>
										{d}
									</option>
								))}
							</select>
						</label>
					) : (
						<label className="flex flex-col gap-1 text-sm font-semibold text-slate-800">
							Support ticket
							<select
								required={!standaloneInternal}
								disabled={ticketPickerDisabled}
								className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-slate-900 disabled:opacity-60"
								value={supportTicket}
								onChange={(e) => setSupportTicket(e.target.value)}
							>
								<option value="">Select ticket…</option>
								{tickets.map((t) => (
									<option key={t.name} value={t.name}>
										{t.name} — {t.subject || "(no subject)"}
									</option>
								))}
							</select>
						</label>
					)}

					<label className="flex flex-col gap-1 text-sm font-semibold text-slate-800">
						Task title
						<input
							required
							className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
							value={subject}
							onChange={(e) => setSubject(e.target.value)}
							placeholder="e.g. Server installation — phase 2"
						/>
					</label>

					<label className="flex flex-col gap-1 text-sm font-semibold text-slate-800">
						Task type
						<select
							className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-slate-900"
							value={taskType}
							onChange={(e) => setTaskType(e.target.value)}
						>
							{TASK_TYPES.map((t) => (
								<option key={t} value={t}>
									{t}
								</option>
							))}
						</select>
					</label>

					<label className="flex flex-col gap-1 text-sm font-semibold text-slate-800">
						Description (optional)
						<textarea
							className="min-h-[100px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Steps, context, acceptance criteria…"
							rows={4}
							disabled={saving}
						/>
					</label>

					<fieldset className="space-y-2 rounded-xl border border-slate-100 bg-slate-50/80 p-4">
						<legend className="px-1 text-xs font-bold uppercase tracking-wide text-slate-500">Responsibility</legend>
						<label className="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
							<input
								type="radio"
								name="responsible_side"
								className="mt-1"
								checked={responsibleSide === "Printechs"}
								onChange={() => setResponsibleSide("Printechs")}
								disabled={saving}
							/>
							<span>
								<span className="font-semibold">Printechs</span>
								<span className="block text-slate-600">Your team owns this work — assign one or more people below.</span>
							</span>
						</label>
						<label className="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
							<input
								type="radio"
								name="responsible_side"
								className="mt-1"
								checked={responsibleSide === "Customer"}
								onChange={() => setResponsibleSide("Customer")}
								disabled={saving}
							/>
							<span>
								<span className="font-semibold">Customer</span>
								<span className="block text-slate-600">
									The customer must act — linked from the ticket when one is selected.
								</span>
							</span>
						</label>
					</fieldset>

					{responsibleSide === "Customer" ? (
						<div className="rounded-xl border border-sky-100 bg-sky-50/80 px-4 py-3 text-sm text-slate-800">
							<p className="text-xs font-bold uppercase tracking-wide text-sky-800/90">Customer</p>
							{standaloneInternal ? (
								<p className="mt-1 text-slate-600">
									No ticket linked — customer responsibility applies when the task is linked to a support ticket.
								</p>
							) : ticketCustomer || ticketCustomerName ? (
								<p className="mt-1 font-medium text-slate-900">
									{ticketCustomerName || ticketCustomer}
									{ticketCustomerName && ticketCustomer ? (
										<span className="ml-1 font-normal text-slate-600">({ticketCustomer})</span>
									) : null}
								</p>
							) : supportTicket.trim() ? (
								<p className="mt-1 text-amber-900">Loading customer…</p>
							) : (
								<p className="mt-1 text-slate-600">Select a support ticket to link the customer.</p>
							)}
						</div>
					) : (
						<div className="rounded-2xl border border-violet-200/90 bg-gradient-to-br from-violet-50/90 to-indigo-50/40 p-5 shadow-sm">
							<h2 className="font-['Syne',system-ui,sans-serif] text-base font-bold text-violet-950">Task assignment</h2>
							<p className="mt-1 text-xs text-violet-900/85">
								Who will do this work? Primary assignee plus optional co-assignees (same as on the task detail page).
							</p>
							<div className="mt-4 space-y-4">
								<label className="flex flex-col gap-1">
									<span className="text-xs font-bold uppercase tracking-wide text-violet-900/80">Primary assignee</span>
									<select
										className="rounded-xl border border-violet-200/80 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-violet-400"
										value={assignPrimary}
										onChange={(e) => {
											const v = e.target.value;
											setAssignPrimary(v);
											setAssignCo((c) => c.filter((x) => x !== v));
										}}
										disabled={saving || assignUsersLoading}
									>
										<option value="">— Unassigned —</option>
										{assignUsers.map((u) => (
											<option key={u.name} value={u.name}>
												{portalAssignmentUserLabel(u)}
											</option>
										))}
									</select>
								</label>
								<div>
									<span className="text-xs font-bold uppercase tracking-wide text-violet-900/80">Also assigned</span>
									{assignUsersLoading ? (
										<p className="mt-2 text-xs text-violet-800/90">Loading assignable users…</p>
									) : assignUsers.length === 0 ? (
										<p className="mt-2 text-xs text-amber-900/90">
											No assignable users returned. Check portal assignment settings or set assignees in Desk after
											creating the task.
										</p>
									) : (
										<ul className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-xl border border-violet-100 bg-white/90 p-2">
											{assignUsers
												.filter((u) => u.name !== assignPrimary)
												.map((u) => (
													<li key={u.name}>
														<label className="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
															<input
																type="checkbox"
																checked={assignCo.includes(u.name)}
																onChange={() => toggleCoAssignee(u.name)}
																disabled={saving}
															/>
															<span>{portalAssignmentUserLabel(u)}</span>
														</label>
													</li>
												))}
										</ul>
									)}
								</div>
							</div>
						</div>
					)}

					<label className="flex flex-col gap-1 text-sm font-semibold text-slate-800">
						Due (optional)
						<input
							type="datetime-local"
							className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
							value={dueDate}
							onChange={(e) => setDueDate(e.target.value)}
							disabled={saving}
						/>
					</label>

					<div className="flex flex-wrap gap-3 pt-2">
						<button
							type="submit"
							disabled={saving || (!standaloneInternal && !canSubmit)}
							className="inline-flex items-center rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
						>
							{saving ? "Creating…" : "Create task"}
						</button>
						<Link to="/tasks" className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm">
							Cancel
						</Link>
					</div>
					{!standaloneInternal && !tickets.length ? (
						<p className="text-sm text-amber-800">
							No open tickets in your portal scope. Resolve or reopen tickets in Desk as needed, or use an internal
							task without a ticket.
						</p>
					) : null}
				</form>
			</section>
		</div>
	);
}
