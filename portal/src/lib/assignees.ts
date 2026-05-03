/** Format task/ticket assignee list from API (assigned_users + legacy primary field). */
export function formatPortalAssignees(row: Record<string, unknown>): string {
	const users = row.assigned_users;
	if (Array.isArray(users) && users.length > 0) {
		return users.map((u) => String(u)).join(", ");
	}
	const one = row.assigned_to_user ?? row.assigned_to;
	if (one != null && String(one).trim() !== "") {
		return String(one);
	}
	return "—";
}
