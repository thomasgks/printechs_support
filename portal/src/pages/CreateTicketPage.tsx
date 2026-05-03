import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
	createPortalTicket,
	getPortalBootstrap,
	getPortalTicketCustomers,
	getPortalTicketTypes,
	portalTicketPath,
	type PortalBootstrapResult,
	type PortalTicketCustomerRow,
	type PortalTicketTypeRow,
} from "../api";

const PRIORITIES = ["Low", "Medium", "High", "Critical"] as const;

/** True when Frappe cannot resolve the RPC. Do not match on method names alone — server errors often include ``create_portal_ticket`` in the text. */
function frappeRpcMethodMissing(message: string): boolean {
	return message.toLowerCase().includes("failed to get method");
}

export default function CreateTicketPage() {
	const navigate = useNavigate();
	const [bootstrap, setBootstrap] = useState<Extract<PortalBootstrapResult, { logged_in: true }> | null>(null);
	const [customers, setCustomers] = useState<PortalTicketCustomerRow[]>([]);
	const [ticketTypes, setTicketTypes] = useState<PortalTicketTypeRow[]>([]);
	const [ticketType, setTicketType] = useState("");
	const [subject, setSubject] = useState("");
	const [description, setDescription] = useState("");
	const [priority, setPriority] = useState<string>("Medium");
	const [customer, setCustomer] = useState("");
	/** Desk/internal portal users only — Internal = test ticket without Customer. */
	const [workScope, setWorkScope] = useState<"customer" | "internal">("customer");
	const [loading, setLoading] = useState(true);
	const [typesLoading, setTypesLoading] = useState(false);
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
				const allowed = b.customers ?? [];
				if (!b.internal) {
					if (!c) {
						setCustomers(allowed.map((name) => ({ name, customer_name: name })));
						if (allowed.length === 1) {
							setCustomer(allowed[0]);
						}
					}
				} else {
					const rows = await getPortalTicketCustomers();
					if (!c) {
						setCustomers(rows.customers ?? []);
					}
				}
			} catch (e) {
				if (!c) {
					const msg = e instanceof Error ? e.message : "Could not load";
					setErr(
						frappeRpcMethodMissing(msg)
							? "This screen needs an updated Printechs Support app on the server (get_portal_ticket_customers). Ask an administrator to git pull, bench migrate, and bench restart."
							: msg,
					);
				}
			} finally {
				if (!c) setLoading(false);
			}
		})();
		return () => {
			c = true;
		};
	}, []);

	const internal = Boolean(bootstrap?.internal);
	const needPickCustomer =
		internal && workScope === "internal"
			? false
			: internal
				? true
				: (bootstrap?.customers?.length ?? 0) > 1;

	const customerForTicketTypes = useMemo((): string | undefined => {
		if (!bootstrap?.logged_in) return undefined;
		if (internal && workScope === "internal") {
			return undefined;
		}
		if (internal) {
			return customer.trim() || undefined;
		}
		const ac = bootstrap.customers ?? [];
		if (ac.length === 1) {
			return ac[0];
		}
		return customer.trim() || undefined;
	}, [bootstrap, internal, customer, workScope]);

	useEffect(() => {
		if (!bootstrap?.logged_in) {
			return;
		}
		let c = false;
		(async () => {
			setTypesLoading(true);
			try {
				const typesRes = await getPortalTicketTypes(customerForTicketTypes);
				if (!c) {
					const types = typesRes.types ?? [];
					setTicketTypes(types);
					setTicketType((prev) => {
						if (types.length === 1) {
							return types[0].name;
						}
						if (prev && types.some((t) => t.name === prev)) {
							return prev;
						}
						return "";
					});
				}
			} catch (e) {
				if (!c) {
					setErr(e instanceof Error ? e.message : "Could not load ticket types");
				}
			} finally {
				if (!c) setTypesLoading(false);
			}
		})();
		return () => {
			c = true;
		};
	}, [bootstrap?.logged_in, customerForTicketTypes]);

	const onSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setErr(null);
		const sub = subject.trim();
		if (!sub) {
			setErr("Subject is required");
			return;
		}
		const tt = ticketType.trim();
		if (!tt) {
			setErr("Ticket type is required");
			return;
		}
		if (internal && workScope === "customer" && !customer.trim()) {
			setErr("Select a customer");
			return;
		}
		setSaving(true);
		try {
			const res = await createPortalTicket({
				subject: sub,
				description: description.trim() || undefined,
				priority,
				customer: needPickCustomer ? customer.trim() || undefined : undefined,
				ticket_type: tt,
				...(internal && workScope === "internal" ? { work_scope: "Internal" as const } : {}),
			});
			navigate(portalTicketPath(res.name), { replace: true });
		} catch (e) {
			const msg = e instanceof Error ? e.message : "Could not create ticket";
			setErr(
				frappeRpcMethodMissing(msg)
					? "Creating tickets requires an updated Printechs Support app on the server. Ask an administrator to deploy the latest app, run bench migrate, and bench restart."
					: msg,
			);
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return <p className="muted">Loading…</p>;
	}

	if (err && !bootstrap) {
		return (
			<div className="center-stage">
				<div className="card login-card">
					<p className="error-text">{err}</p>
					<p className="muted small">
						<Link to="/tickets">Back to tickets</Link>
					</p>
				</div>
			</div>
		);
	}

	if (bootstrap && !bootstrap.internal && (!bootstrap.customers || bootstrap.customers.length === 0)) {
		return (
			<div className="center-stage">
				<div className="card login-card">
					<h2 className="card-title">Cannot create a ticket</h2>
					<p className="muted">
						No customer is linked to your user. Ask an administrator to assign User Permissions or link your Contact to a Customer.
					</p>
					<p className="muted small">
						<Link to="/tickets">Back to tickets</Link>
					</p>
				</div>
			</div>
		);
	}

	if (bootstrap && !typesLoading && ticketTypes.length === 0) {
		return (
			<div className="center-stage">
				<div className="card login-card">
					<h2 className="card-title">No ticket types available</h2>
					<p className="muted">
						Either no active <strong>Support Ticket Type</strong> exists, or your customer’s <strong>Portal — Allowed Ticket Types</strong> list
						excludes every type. Ask an administrator to review Support Ticket Types and the customer mapping.
					</p>
					<p className="muted small">
						<Link to="/tickets">Back to tickets</Link>
					</p>
				</div>
			</div>
		);
	}

	return (
		<div className="page-grid max-w-2xl gap-6">
			<p className="detail-back">
				<Link to="/tickets" className="btn-text">
					← Tickets
				</Link>
			</p>

			<section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-saas">
				<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">New support ticket</h1>
				<p className="mt-2 text-sm text-slate-600">
					{internal ? (
						<>
							Choose <strong>Internal test</strong> for training and app checks (no customer). Choose{" "}
							<strong>Customer ticket</strong> for normal client-linked work. The ticket is created in ERPNext with the usual initial
							status.
						</>
					) : (
						<>
							Describe the issue. Your ticket is created in ERPNext with the <strong>initial status</strong> defined for new tickets (for
							example Open, or Draft if a workflow applies) and is visible to your team.
						</>
					)}
				</p>

				<form className="mt-8 flex flex-col gap-5" onSubmit={(e) => void onSubmit(e)}>
					{internal ? (
						<fieldset className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
							<legend className="px-1 text-xs font-bold uppercase tracking-wide text-indigo-800">Work scope</legend>
							<label className="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
								<input
									type="radio"
									className="mt-1"
									name="portal_ticket_work_scope"
									checked={workScope === "customer"}
									onChange={() => setWorkScope("customer")}
									disabled={saving}
								/>
								<span>
									<span className="font-semibold">Customer ticket</span>
									<span className="block text-slate-600">Linked to a customer — normal support.</span>
								</span>
							</label>
							<label className="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
								<input
									type="radio"
									className="mt-1"
									name="portal_ticket_work_scope"
									checked={workScope === "internal"}
									onChange={() => {
										setWorkScope("internal");
										setCustomer("");
									}}
									disabled={saving}
								/>
								<span>
									<span className="font-semibold">Internal test</span>
									<span className="block text-slate-600">No customer — use for demos, QA, and internal testing.</span>
								</span>
							</label>
						</fieldset>
					) : null}
					{needPickCustomer ? (
						<label className="flex flex-col gap-1.5">
							<span className="text-xs font-bold uppercase tracking-wide text-slate-500">Customer</span>
							<select
								className="rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm font-medium text-slate-900 outline-none ring-blue-500/15 focus:border-blue-400 focus:bg-white focus:ring-4"
								required
								value={customer}
								onChange={(e) => setCustomer(e.target.value)}
								disabled={saving}
							>
								<option value="">Select customer…</option>
								{customers.map((row) => (
									<option key={row.name} value={row.name}>
										{row.customer_name}
									</option>
								))}
							</select>
						</label>
					) : !internal && bootstrap?.customers?.[0] ? (
						<p className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-700">
							<span className="font-semibold text-slate-800">Customer: </span>
							{bootstrap.customers[0]}
						</p>
					) : null}

					<label className="flex flex-col gap-1.5">
						<span className="text-xs font-bold uppercase tracking-wide text-slate-500">Ticket type *</span>
						<select
							className="rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm font-medium text-slate-900 outline-none ring-blue-500/15 focus:border-blue-400 focus:bg-white focus:ring-4"
							required
							value={ticketType}
							onChange={(e) => setTicketType(e.target.value)}
							disabled={saving || typesLoading}
						>
							<option value="">{typesLoading ? "Loading ticket types…" : "Select ticket type…"}</option>
							{ticketTypes.map((t) => (
								<option key={t.name} value={t.name}>
									{t.label}
									{t.division ? ` (${t.division})` : ""}
								</option>
							))}
						</select>
					</label>

					<label className="flex flex-col gap-1.5">
						<span className="text-xs font-bold uppercase tracking-wide text-slate-500">Subject</span>
						<input
							type="text"
							className="rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm text-slate-900 outline-none ring-blue-500/15 focus:border-blue-400 focus:bg-white focus:ring-4"
							placeholder="Short summary of the request"
							value={subject}
							onChange={(e) => setSubject(e.target.value)}
							disabled={saving}
							required
							maxLength={500}
						/>
					</label>

					<label className="flex flex-col gap-1.5">
						<span className="text-xs font-bold uppercase tracking-wide text-slate-500">Details</span>
						<textarea
							className="min-h-[8rem] resize-y rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm text-slate-900 outline-none ring-blue-500/15 focus:border-blue-400 focus:bg-white focus:ring-4"
							placeholder="What happened, steps to reproduce, site or device, urgency…"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							disabled={saving}
						/>
					</label>

					<label className="flex flex-col gap-1.5">
						<span className="text-xs font-bold uppercase tracking-wide text-slate-500">Priority</span>
						<select
							className="rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm font-medium text-slate-900 outline-none ring-blue-500/15 focus:border-blue-400 focus:bg-white focus:ring-4"
							value={priority}
							onChange={(e) => setPriority(e.target.value)}
							disabled={saving}
						>
							{PRIORITIES.map((p) => (
								<option key={p} value={p}>
									{p}
								</option>
							))}
						</select>
					</label>

					{err ? <p className="text-sm text-red-600">{err}</p> : null}

					<div className="flex flex-wrap gap-3 pt-2">
						<button type="submit" className="portal-btn-primary rounded-xl px-6 py-3 text-sm font-bold" disabled={saving}>
							{saving ? "Creating…" : "Create ticket"}
						</button>
						<Link to="/tickets" className="inline-flex items-center rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300">
							Cancel
						</Link>
					</div>
				</form>
			</section>
		</div>
	);
}
