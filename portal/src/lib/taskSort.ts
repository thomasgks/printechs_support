export type PortalTaskSort = "task" | "due_date" | "last_update" | "ticket";

export const PORTAL_TASK_SORT_OPTIONS: { value: PortalTaskSort; label: string; default?: boolean }[] = [
	{ value: "task", label: "Task", default: true },
	{ value: "due_date", label: "Due date" },
	{ value: "last_update", label: "Last update" },
];

const STORAGE_KEY = "portal-task-sort";

export function readPortalTaskSortPreference(): PortalTaskSort {
	try {
		const v = localStorage.getItem(STORAGE_KEY);
		if (v === "due_date" || v === "last_update") return v;
		if (v === "task") return "task";
		if (v === "ticket") {
			localStorage.setItem(STORAGE_KEY, "task");
			return "task";
		}
	} catch {
		/* ignore */
	}
	return "task";
}

export function writePortalTaskSortPreference(sort: PortalTaskSort): void {
	try {
		localStorage.setItem(STORAGE_KEY, sort);
	} catch {
		/* ignore */
	}
}

function parseSortTime(value: unknown): number | null {
	if (value == null || value === "") return null;
	const t = new Date(String(value)).getTime();
	return Number.isNaN(t) ? null : t;
}

/** Client-side sort (mock mode and kanban/table after fetch). */
export function sortPortalTasks(rows: Record<string, unknown>[], sort: PortalTaskSort): Record<string, unknown>[] {
	const copy = [...rows];
	const byName = (a: Record<string, unknown>, b: Record<string, unknown>) =>
		String(a.name ?? "").localeCompare(String(b.name ?? ""));

	switch (sort) {
		case "due_date":
			return copy.sort((a, b) => {
				const da = parseSortTime(a.due_date);
				const db = parseSortTime(b.due_date);
				if (da == null && db == null) return byName(a, b);
				if (da == null) return 1;
				if (db == null) return -1;
				if (da !== db) return da - db;
				return byName(a, b);
			});
		case "last_update":
			return copy.sort((a, b) => {
				const ma = parseSortTime(a.modified) ?? 0;
				const mb = parseSortTime(b.modified) ?? 0;
				if (ma !== mb) return mb - ma;
				return byName(a, b);
			});
		case "ticket":
			return copy.sort((a, b) => {
				const ta = String(a.support_ticket ?? "\uffff");
				const tb = String(b.support_ticket ?? "\uffff");
				const cmp = ta.localeCompare(tb);
				if (cmp !== 0) return cmp;
				return byName(a, b);
			});
		default:
			return copy.sort(byName);
	}
}
