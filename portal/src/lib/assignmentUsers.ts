import type { PortalAssignmentUserRow } from "../api";

/** Portal assignment picker label (disambiguates duplicate full names). */
export function portalAssignmentUserLabel(u: PortalAssignmentUserRow): string {
	return (u.label || u.full_name || u.name || "").trim() || u.name;
}
