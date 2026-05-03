import { useEffect, useState } from "react";

type Props = {
	label: string;
	value: string;
	options: string[];
	disabled?: boolean;
	onSave: (next: string) => Promise<void>;
};

export default function StatusSelect({ label, value, options, disabled, onSave }: Props) {
	const [saving, setSaving] = useState(false);
	const [local, setLocal] = useState(value);
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		setLocal(value);
	}, [value]);

	return (
		<div className="flex flex-wrap items-center gap-3">
			<label className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</label>
			<div className="flex flex-wrap items-center gap-2">
				<select
					className="min-w-[12rem] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm outline-none ring-violet-500/20 focus:border-violet-400 focus:ring-4 disabled:opacity-50"
					value={local}
					disabled={disabled || saving}
					onChange={(e) => setLocal(e.target.value)}
				>
					{options.map((o) => (
						<option key={o} value={o}>
							{o}
						</option>
					))}
				</select>
				<button
					type="button"
					className="portal-btn-primary rounded-xl px-4 py-2 text-sm font-bold shadow-md transition hover:brightness-105"
					disabled={disabled || saving || local === value}
					onClick={async () => {
						setErr(null);
						setSaving(true);
						try {
							await onSave(local);
						} catch (e) {
							setErr(e instanceof Error ? e.message : "Could not update");
						} finally {
							setSaving(false);
						}
					}}
				>
					{saving ? "Saving…" : "Update"}
				</button>
			</div>
			{err ? <span className="text-sm text-red-600">{err}</span> : null}
		</div>
	);
}
