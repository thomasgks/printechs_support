import { useEffect, useState } from "react";
import { updatePortalTaskAssignment, type PortalAssignmentUserRow } from "../api";

type Props = {
	taskName: string;
	initialAssignees: string[];
	users: PortalAssignmentUserRow[];
	onUpdated: (patch: Record<string, unknown>) => void;
};

export default function TechnicianTaskAssignment({ taskName, initialAssignees, users, onUpdated }: Props) {
	const [primary, setPrimary] = useState(initialAssignees[0] || "");
	const [co, setCo] = useState<string[]>(initialAssignees.slice(1));
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		setPrimary(initialAssignees[0] || "");
		setCo(initialAssignees.slice(1));
	}, [taskName, initialAssignees.join("|")]);

	function toggleCo(name: string) {
		if (name === primary) return;
		setCo((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
	}

	async function save() {
		setErr(null);
		const list = [primary, ...co.filter((x) => x && x !== primary)].filter(Boolean);
		setBusy(true);
		try {
			const r = await updatePortalTaskAssignment(taskName, JSON.stringify(list));
			onUpdated({
				assigned_to_user: r.assigned_to_user,
				assigned_users: r.assigned_users,
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
		<div className="rounded-2xl border border-violet-200/90 bg-gradient-to-br from-violet-50/90 to-indigo-50/40 p-5 shadow-sm">
			<h3 className="font-['Syne',system-ui,sans-serif] text-base font-bold text-violet-950">Technician assignment</h3>
			<p className="mt-1 text-xs text-violet-900/85">
				Assign this task from the portal (Desk not required). Primary may be empty until you route work.
			</p>
			{users.length === 0 ? (
				<p className="mt-3 rounded-xl border border-amber-200 bg-amber-50/95 px-3 py-2 text-xs leading-snug text-amber-950">
					No users matched the portal assignment roles. You can still save to clear assignees; otherwise add roles or assign in Desk.
				</p>
			) : null}
			<div className="mt-4 flex flex-col gap-4">
				<label className="flex flex-col gap-1">
					<span className="text-xs font-bold uppercase tracking-wide text-violet-900/80">Primary assignee</span>
					<select
						className="rounded-xl border border-violet-200/80 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-violet-400"
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
					<span className="text-xs font-bold uppercase tracking-wide text-violet-900/80">Also assigned</span>
					<ul className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-xl border border-violet-100 bg-white/90 p-2">
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
				{busy ? "Saving…" : "Save assignees"}
			</button>
		</div>
	);
}
