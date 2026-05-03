import { statusBadgeClasses } from "../lib/status";

const STEPS = [
	{ key: "open", label: "Open" },
	{ key: "progress", label: "In progress" },
	{ key: "wait", label: "Waiting" },
	{ key: "done", label: "Completed" },
] as const;

function stepIndex(status: string): number {
	const s = status.trim().toLowerCase();
	if (s === "completed" || s === "cancelled") return 3;
	if (s === "waiting for customer" || s === "waiting for printechs" || s === "delayed") return 2;
	if (s === "in progress") return 1;
	return 0;
}

type Props = { status: string };

export default function TaskProgressStepper({ status }: Props) {
	const active = stepIndex(status);
	return (
		<div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 shadow-saas">
			<p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Lifecycle</p>
			<ol className="grid grid-cols-2 gap-3 sm:grid-cols-4">
				{STEPS.map((step, i) => {
					const done = i < active;
					const current = i === active;
					return (
						<li key={step.key} className="flex flex-col items-center gap-1 text-center">
							<span
								className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold ring-2 ring-offset-2 ring-offset-slate-50 ${
									done
										? "bg-emerald-500 text-white ring-emerald-400"
										: current
											? "bg-blue-600 text-white ring-blue-300"
											: "bg-white text-slate-400 ring-slate-200"
								}`}
							>
								{done ? "✓" : i + 1}
							</span>
							<span
								className={`text-[0.65rem] font-semibold uppercase tracking-wide sm:text-xs ${
									current ? "text-blue-800" : "text-slate-500"
								}`}
							>
								{step.label}
							</span>
						</li>
					);
				})}
			</ol>
			<p className="mt-3 text-center text-xs text-slate-600">
				Current status:{" "}
				<span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${statusBadgeClasses(status)}`}>
					{status}
				</span>
			</p>
		</div>
	);
}
