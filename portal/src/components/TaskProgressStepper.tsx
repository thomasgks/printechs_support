import { statusBadgeClasses } from "../lib/status";

const STEPS = [
	{ key: "open", label: "Open" },
	{ key: "progress", label: "In progress" },
	{ key: "wait", label: "Waiting" },
	{ key: "pause", label: "Delayed" },
	{ key: "done", label: "Completed" },
] as const;

function stepIndex(status: string): number {
	const s = status.trim().toLowerCase();
	if (s === "completed" || s === "cancelled") return 4;
	if (s === "delayed" || s === "hold") return 3;
	if (s === "waiting for customer" || s === "waiting for printechs") return 2;
	if (s === "in progress") return 1;
	return 0;
}

function activeStepClasses(stepKey: string): string {
	if (stepKey === "pause") {
		return "bg-yellow-400 text-yellow-950";
	}
	return "bg-blue-600 text-white";
}

function stepTextClasses(stepKey: string, current: boolean, done: boolean): string {
	if (current && stepKey === "pause") {
		return "text-yellow-800";
	}
	if (current) {
		return "text-blue-800";
	}
	if (done) {
		return "text-emerald-700";
	}
	return "text-slate-400";
}

type Props = { status: string; embedded?: boolean };

export default function TaskProgressStepper({ status, embedded = false }: Props) {
	const active = stepIndex(status);
	if (embedded) {
		return (
			<div className="rounded-2xl bg-white/40 px-4 py-3 ring-1 ring-white/60 backdrop-blur">
				<div className="mb-2 flex flex-wrap items-center justify-between gap-2">
					<p className="text-[0.65rem] font-bold uppercase tracking-[0.18em] text-slate-500">Lifecycle</p>
					<span className={`inline-flex rounded-full px-2 py-0.5 text-[0.65rem] font-bold ring-1 ${statusBadgeClasses(status)}`}>
						{status}
					</span>
				</div>
				<ol className="grid grid-cols-5 items-start">
					{STEPS.map((step, i) => {
						const done = i < active;
						const current = i === active;
						const terminalCurrent = current && step.key === "done";
						return (
							<li key={step.key} className="relative flex flex-col items-center text-center">
								{i > 0 ? (
									<span
										className={`absolute left-0 top-4 h-0.5 w-1/2 -translate-y-1/2 ${
											i <= active ? "bg-emerald-300" : "bg-slate-200/80"
										}`}
									/>
								) : null}
								{i < STEPS.length - 1 ? (
									<span
										className={`absolute right-0 top-4 h-0.5 w-1/2 -translate-y-1/2 ${
											i < active ? "bg-emerald-300" : "bg-slate-200/80"
										}`}
									/>
								) : null}
								<span
									className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold shadow-sm ring-4 ring-white/80 ${
										done || terminalCurrent
											? "bg-emerald-500 text-white"
											: current
												? activeStepClasses(step.key)
												: "bg-white text-slate-400 ring-slate-100"
									}`}
								>
									{done || terminalCurrent ? "✓" : step.key === "pause" && current ? "!" : i + 1}
								</span>
								<span
									className={`mt-1 text-[0.62rem] font-bold uppercase tracking-wide ${stepTextClasses(step.key, current, done || terminalCurrent)}`}
								>
									{step.label}
								</span>
							</li>
						);
					})}
				</ol>
			</div>
		);
	}
	return (
		<div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 shadow-saas">
			<p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Lifecycle</p>
			<ol className="grid grid-cols-2 gap-3 sm:grid-cols-5">
				{STEPS.map((step, i) => {
					const done = i < active;
					const current = i === active;
					const terminalCurrent = current && step.key === "done";
					return (
						<li key={step.key} className="flex flex-col items-center gap-1 text-center">
							<span
								className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold ring-2 ring-offset-2 ring-offset-slate-50 ${
									done || terminalCurrent
										? "bg-emerald-500 text-white ring-emerald-400"
										: current
											? `${activeStepClasses(step.key)} ${step.key === "pause" ? "ring-yellow-300" : "ring-blue-300"}`
											: "bg-white text-slate-400 ring-slate-200"
								}`}
							>
								{done || terminalCurrent ? "✓" : step.key === "pause" && current ? "!" : i + 1}
							</span>
							<span
								className={`text-[0.65rem] font-semibold uppercase tracking-wide sm:text-xs ${stepTextClasses(step.key, current, done || terminalCurrent)}`}
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
