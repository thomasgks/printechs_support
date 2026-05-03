/**
 * Maps Support Task / ticket status strings to Tailwind class bundles (portal design system).
 */

const STATUS_NORMALIZE: Record<string, string> = {
	"waiting for customer": "waitcust",
	"waiting for printechs": "waitint",
	"waiting for internal team": "waitint",
	"in progress": "progress",
	completed: "done",
	cancelled: "new",
	delayed: "waitcust",
	open: "open",
	new: "new",
};

export function statusVisualKey(status: string): string {
	const k = status.trim().toLowerCase();
	return STATUS_NORMALIZE[k] ?? "open";
}

/** Tailwind classes for badge (bg, text, ring) */
export function statusBadgeClasses(status: string): string {
	const key = statusVisualKey(status);
	switch (key) {
		case "new":
			return "bg-slate-100 text-slate-700 ring-slate-200";
		case "open":
			return "bg-blue-100 text-blue-800 ring-blue-200";
		case "progress":
			return "bg-indigo-100 text-indigo-800 ring-indigo-200";
		case "waitcust":
			return "bg-amber-100 text-amber-900 ring-amber-200";
		case "waitint":
			return "bg-purple-100 text-purple-900 ring-purple-200";
		case "done":
			return "bg-emerald-100 text-emerald-900 ring-emerald-200";
		default:
			return "bg-slate-100 text-slate-700 ring-slate-200";
	}
}

export function priorityBadgeClasses(priority: string): string {
	const p = priority.trim().toLowerCase();
	if (p === "critical" || p === "urgent") return "bg-red-100 text-red-900 ring-red-200";
	if (p === "high") return "bg-orange-100 text-orange-900 ring-orange-200";
	if (p === "medium") return "bg-amber-50 text-amber-900 ring-amber-100";
	if (p === "low") return "bg-slate-100 text-slate-700 ring-slate-200";
	return "bg-slate-100 text-slate-600 ring-slate-200";
}

/**
 * Ensures the document's current status appears in the status dropdown options when the API returns
 * a restricted list (e.g. customer portal) that omits read-only states like Draft or Closed.
 */
export function mergeStatusOptions(current: string, apiOptions: string[]): string[] {
	const cur = String(current ?? "").trim();
	const fromApi = Array.isArray(apiOptions) ? apiOptions.filter((o) => String(o).trim() !== "") : [];
	if (!fromApi.length) {
		return cur ? [cur] : [];
	}
	if (!cur || fromApi.includes(cur)) {
		return fromApi;
	}
	return [cur, ...fromApi];
}
