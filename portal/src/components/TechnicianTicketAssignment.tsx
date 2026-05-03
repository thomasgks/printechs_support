import { useEffect, useState } from "react";
import {
	updatePortalTicketAssignment,
	type PortalAssignmentUserRow,
	type PortalTeamRow,
} from "../api";

type Props = {
	ticketName: string;
	initialTeam: string;
	initialAssignees: string[];
	teams: PortalTeamRow[];
	users: PortalAssignmentUserRow[];
	onUpdated: (patch: Record<string, unknown>) => void;
};

export default function TechnicianTicketAssignment({
	ticketName,
	initialTeam,
	initialAssignees,
	teams,
	users,
	onUpdated,
}: Props) {
	const [team, setTeam] = useState(initialTeam || "");
	const [primary, setPrimary] = useState(initialAssignees[0] || "");
	const [co, setCo] = useState<string[]>(initialAssignees.slice(1));
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		setTeam(initialTeam || "");
		setPrimary(initialAssignees[0] || "");
		setCo(initialAssignees.slice(1));
	}, [ticketName, initialTeam, initialAssignees.join("|")]);

	function toggleCo(name: string) {
		if (name === primary) return;
		setCo((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
	}

	async function save() {
		setErr(null);
		const list = [primary, ...co.filter((x) => x && x !== primary)].filter(Boolean);
		setBusy(true);
		try {
			const r = await updatePortalTicketAssignment(ticketName, {
				team,
				assignees: JSON.stringify(list),
			});
			onUpdated({
				team: r.team,
				assigned_to: r.assigned_to,
				assigned_users: r.assigned_users,
				status: r.status,
			});
			setPrimary(r.assigned_users[0] || "");
			setCo(r.assigned_users.slice(1));
		} catch (e) {
			setErr(e instanceof Error ? e.message : "Could not save");
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="rounded-2xl border border-indigo-200/90 bg-gradient-to-br from-indigo-50/90 to-violet-50/50 p-5 shadow-sm">
			<h3 className="font-['Syne',system-ui,sans-serif] text-base font-bold text-indigo-950">Technician routing</h3>
			<p className="mt-1 text-xs text-indigo-900/80">
				Set team and assignees here — no need to open Desk. First assignee is primary (owner for lists and notifications).
				Primary can stay unassigned until routing is decided; saving with no assignees clears ownership.
			</p>
			{users.length === 0 ? (
				<p className="mt-3 rounded-xl border border-amber-200 bg-amber-50/95 px-3 py-2 text-xs leading-snug text-amber-950">
					No users matched the portal assignment roles (Support Engineer, Coordinator, Project Manager, Support Team).
					You can still update <strong className="font-semibold">Team</strong> or clear assignees. Add those roles to users or assign in Desk.
				</p>
			) : null}
			<div className="mt-4 flex flex-col gap-4">
				<label className="flex flex-col gap-1">
					<span className="text-xs font-bold uppercase tracking-wide text-indigo-800/80">Team</span>
					<select
						className="rounded-xl border border-indigo-200/80 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-400"
						value={team}
						onChange={(e) => setTeam(e.target.value)}
						disabled={busy}
					>
						<option value="">— None —</option>
						{teams.map((t) => (
							<option key={t.name} value={t.name}>
								{t.label}
							</option>
						))}
					</select>
				</label>
				<label className="flex flex-col gap-1">
					<span className="text-xs font-bold uppercase tracking-wide text-indigo-800/80">Primary assignee</span>
					<select
						className="rounded-xl border border-indigo-200/80 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-400"
						value={primary}
						onChange={(e) => {
							const v = e.target.value;
							setPrimary(v);
							setCo((c) => c.filter((x) => x !== v));
						}}
						disabled={busy}
					>
						<option value="">— Unassigned —</option>
						{users.map((u) => (
							<option key={u.name} value={u.name}>
								{u.full_name || u.name}
							</option>
						))}
					</select>
				</label>
				<div>
					<span className="text-xs font-bold uppercase tracking-wide text-indigo-800/80">Also assigned</span>
					<ul className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-xl border border-indigo-100 bg-white/90 p-2">
						{users
							.filter((u) => u.name !== primary)
							.map((u) => (
								<li key={u.name}>
									<label className="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
										<input
											type="checkbox"
											checked={co.includes(u.name)}
											onChange={() => toggleCo(u.name)}
											disabled={busy}
										/>
										<span>{u.full_name || u.name}</span>
									</label>
								</li>
							))}
					</ul>
				</div>
			</div>
			{err ? <p className="mt-3 text-sm text-red-600">{err}</p> : null}
			<button
				type="button"
				className="portal-btn-primary mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-bold sm:w-auto"
				disabled={busy}
				onClick={() => void save()}
			>
				{busy ? "Saving…" : "Save assignment"}
			</button>
		</div>
	);
}
