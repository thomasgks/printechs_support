import {
	isPortalMockDataEnabled,
	MOCK_DASHBOARD_STATS,
	mockPortalTask,
	mockPortalTicket,
	MOCK_PORTAL_BOOTSTRAP,
	MOCK_PORTAL_TASKS,
	MOCK_PORTAL_TICKETS,
} from "./portalMock";
import type { PortalComment, PortalFileRow } from "./types/portal";

export { isPortalMockDataEnabled };
export type { PortalComment, PortalFileRow } from "./types/portal";

/** Frappe API base (Option C). Empty = same origin as the SPA (embedded or dev proxy). */
export function getApiBase(): string {
	const v = import.meta.env.VITE_FRAPPE_SITE_URL;
	if (typeof v === "string" && v.trim()) {
		return v.replace(/\/$/, "");
	}
	return "";
}

/** True when the SPA runs on a different origin than the Frappe site (separate deploy). */
export function isStandalonePortal(): boolean {
	const base = getApiBase();
	if (!base) {
		return false;
	}
	try {
		return new URL(base).origin !== window.location.origin;
	} catch {
		return false;
	}
}

/** Origin of the bench (ERPNext / Frappe site) for /login, portal logout cmd, /support-tickets, etc. */
export function getFrappeSiteOrigin(): string {
	const b = getApiBase();
	if (b) {
		try {
			return new URL(b).origin;
		} catch {
			/* fall through */
		}
	}
	return window.location.origin;
}

/** Absolute URL to a route on the Frappe website (web forms, logout). */
export function frappeWebPath(path: string): string {
	const p = path.startsWith("/") ? path : `/${path}`;
	return `${getFrappeSiteOrigin()}${p}`;
}

function apiUrl(path: string): string {
	const base = getApiBase();
	if (!base) {
		return path.startsWith("/") ? path : `/${path}`;
	}
	const p = path.startsWith("/") ? path : `/${path}`;
	return `${base}${p}`;
}

let csrfTokenCache: string | null = null;

export function clearCsrfCache(): void {
	csrfTokenCache = null;
}

function sanitizeExc(exc: string): string {
	const t = exc.replace(/<[^>]*>/g, " ").replace(/&nbsp;/g, " ");
	return t.replace(/\s+/g, " ").trim() || exc;
}

/** Frappe ValidationError uses HTTP 417; user-facing text is often in `_server_messages`, not `exc`. */
function extractFrappeUserMessage(data: Record<string, unknown>): string | null {
	const raw = data._server_messages;
	if (typeof raw !== "string" || !raw.trim()) {
		return null;
	}
	try {
		const outer = JSON.parse(raw) as unknown[];
		for (const item of outer) {
			const inner = typeof item === "string" ? JSON.parse(item) : item;
			if (inner && typeof inner === "object" && "message" in inner && typeof (inner as { message: string }).message === "string") {
				const m = (inner as { message: string }).message.trim();
				if (m) {
					return m;
				}
			}
		}
	} catch {
		return null;
	}
	return null;
}

async function resolveCsrfToken(): Promise<string> {
	if (csrfTokenCache) {
		return csrfTokenCache;
	}
	// Always load CSRF from the bench session via API. Do not use window.frappe.csrf_token here:
	// after portal_login the cookie session changes but the HTML-injected frappe token can still
	// be the old Guest token → Frappe returns HTTP 400 Invalid Request (CSRFTokenError).
	const r = await fetch(
		apiUrl("/api/method/printechs_support.printechs_support_system.api.portal_api.get_portal_csrf_token"),
		{ method: "GET", credentials: "include" },
	);
	let data: { message?: string; exc?: string };
	try {
		data = (await r.json()) as { message?: string; exc?: string };
	} catch {
		throw new Error(`HTTP ${r.status}: could not read response`);
	}
	if (!r.ok || data.exc) {
		throw new Error(sanitizeExc(data.exc || `HTTP ${r.status}`));
	}
	if (!data.message) {
		throw new Error("No CSRF token");
	}
	csrfTokenCache = data.message as string;
	return csrfTokenCache;
}

/** Result of get_portal_bootstrap (allow_guest so unauthenticated users get a clean payload). */
export type PortalBootstrapResult =
	| { logged_in: false }
	| {
			logged_in: true;
			user: string;
			full_name: string;
			customers: string[];
			internal: boolean;
			help_url: string;
			brand_logo?: string;
			brand_name?: string;
	  };

export async function callMethod<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
	const csrf = await resolveCsrfToken();
	const res = await fetch(apiUrl(`/api/method/${encodeURIComponent(method)}`), {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Accept: "application/json",
			"X-Frappe-CSRF-Token": csrf,
		},
		credentials: "include",
		body: JSON.stringify(args),
	});
	let data: {
		message?: T;
		exc?: string;
		exception?: string;
		_exc_source?: string;
		_server_messages?: string;
	};
	try {
		data = (await res.json()) as typeof data;
	} catch {
		throw new Error(`HTTP ${res.status}: invalid response`);
	}
	if (!res.ok) {
		const detail =
			extractFrappeUserMessage(data as Record<string, unknown>) ||
			(data as { message?: string }).message ||
			(data as { exc?: string }).exc ||
			`HTTP ${res.status}`;
		throw new Error(typeof detail === "string" ? sanitizeExc(String(detail)) : String(detail));
	}
	if (data.exc) {
		const detail = extractFrappeUserMessage(data as Record<string, unknown>) || data.exc;
		throw new Error(sanitizeExc(typeof detail === "string" ? detail : String(detail)));
	}
	return data.message as T;
}

/** Password login for the portal SPA (session cookie on the Frappe host). Clears CSRF cache after success. */
export async function portalLogin(usr: string, pwd: string): Promise<void> {
	await callMethod<{ logged_in: boolean }>(
		"printechs_support.printechs_support_system.api.portal_api.portal_login",
		{ usr, pwd },
	);
	clearCsrfCache();
}

export async function portalLogout(): Promise<void> {
	await callMethod<{ logged_out: boolean }>(
		"printechs_support.printechs_support_system.api.portal_api.portal_logout",
	);
	clearCsrfCache();
}

export function portalHomeUrl(): string {
	if (typeof window === "undefined") {
		return "/support-portal";
	}
	return import.meta.env.DEV ? "/" : `${window.location.origin}/support-portal`;
}

export async function completePortalRegistration(key: string, newPassword: string): Promise<void> {
	await callMethod<{ logged_in: boolean; redirect_url?: string }>(
		"printechs_support.printechs_support_system.api.portal_api.complete_portal_registration",
		{ key, new_password: newPassword },
	);
	clearCsrfCache();
}

export function getPortalBootstrap() {
	if (isPortalMockDataEnabled()) {
		return Promise.resolve(MOCK_PORTAL_BOOTSTRAP);
	}
	return callMethod<PortalBootstrapResult>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_bootstrap",
	);
}

export function getPortalTickets(
	limit = 50,
	opts?: { search?: string; activeOnly?: boolean; customer?: string; ticketType?: string },
) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTickets(limit, opts));
	}
	return callMethod<Record<string, unknown>[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_tickets",
		{
			limit,
			search: opts?.search?.trim() || "",
			customer: opts?.customer?.trim() || "",
			ticket_type: opts?.ticketType?.trim() || "",
			// Only exclude closed/resolved when explicitly true (default: show all — matches server default).
			active_only: opts?.activeOnly === true ? 1 : 0,
		},
	);
}

export function createGoogleMeet(ticketId: string) {
	return callMethod<{
		success: boolean;
		meeting_url: string;
		event_id?: string;
		message: string;
		warning?: string | null;
	}>("printechs_support.printechs_support_system.api.google_meet.create_google_meet", {
		ticket_id: ticketId,
		notify_customer: 1,
	});
}

export function resendGoogleMeetLink(ticketId: string) {
	return callMethod<{
		success: boolean;
		meeting_url: string;
		event_id?: string;
		message: string;
		warning?: string | null;
	}>("printechs_support.printechs_support_system.api.google_meet.resend_google_meet_link", {
		ticket_id: ticketId,
	});
}

export function getContextualHelp(args: {
	module_area?: string;
	doctype?: string;
	screen?: string;
	issue_type?: string;
	search?: string;
	customer_view?: number;
	limit?: number;
}) {
	return callMethod<{
		success: boolean;
		articles: Array<{
			name: string;
			title: string;
			summary: string;
			category: string;
			module_area: string;
			related_doctype: string;
			video_url: string;
			has_video: boolean;
			attachments_count: number;
		}>;
	}>("printechs_support.api.help_article.get_contextual_help", args);
}

export function getPortalTasks(limit = 50) {
	if (isPortalMockDataEnabled()) {
		const rows = MOCK_PORTAL_TASKS.slice(0, Math.min(limit, MOCK_PORTAL_TASKS.length));
		return Promise.resolve(
			rows.map((t) => {
				const d = t.due_date;
				const cal =
					typeof d === "string" && d.length >= 10 && d[4] === "-" && d[7] === "-"
						? d.slice(0, 10)
						: null;
				return { ...t, due_date_calendar: cal };
			}),
		);
	}
	return callMethod<Record<string, unknown>[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_tasks",
		{ limit },
	);
}

/** Tasks linked to a ticket (same fields as getPortalTasks). */
export function getPortalTasksForTicket(ticketName: string, limit = 100) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTasksForTicket(ticketName, limit));
	}
	return callMethod<Record<string, unknown>[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_tasks_for_ticket",
		{ ticket_name: ticketName.trim(), limit },
	);
}

export type PortalDashboardStats = {
	pending_tickets: number;
	overdue_tickets: number;
	tickets_waiting_customer: number;
	tickets_waiting_internal: number;
	pending_tasks: number;
	overdue_tasks: number;
	completed_today: number;
	/** Support Task status */
	waiting_customer: number;
	/** Support Task status */
	waiting_internal: number;
	sla_breached: number;
	delayed_flagged: number;
	tickets_by_status: Record<string, number>;
	tasks_by_status: Record<string, number>;
	assignee_load: { name: string; count: number }[];
	monthly_completion: { month: string; label: string; count: number }[];
};

export function getPortalDashboardStats() {
	if (isPortalMockDataEnabled()) {
		return Promise.resolve(MOCK_DASHBOARD_STATS);
	}
	return callMethod<PortalDashboardStats>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_dashboard_stats",
	);
}

/** In-SPA paths (basename e.g. /support-portal is handled by the router). */
export function portalTicketPath(name: string): string {
	return `/tickets/${encodeURIComponent(name)}`;
}

/** Path for creating a new ticket (declare before dynamic `:ticketId` route). */
export function portalTicketNewPath(): string {
	return "/tickets/new";
}

export type PortalTicketCustomerRow = { name: string; customer_name: string };

export function getPortalTicketCustomers() {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTicketCustomers());
	}
	return callMethod<{ customers: PortalTicketCustomerRow[] }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_customers",
	);
}

export type PortalTicketTypeRow = { name: string; label: string; division: string };

export function getPortalTicketTypes(customer?: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTicketTypes(customer));
	}
	return callMethod<{ types: PortalTicketTypeRow[]; restricted?: boolean }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_types",
		{ customer: customer?.trim() ?? "" },
	);
}

export type PortalTeamRow = { name: string; label: string };

export function getPortalTeams() {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTeams());
	}
	return callMethod<{ teams: PortalTeamRow[] }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_teams",
	);
}

export type PortalAssignmentUserRow = { name: string; full_name: string };

export function getPortalAssignmentUsers() {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalAssignmentUsers());
	}
	return callMethod<{ users: PortalAssignmentUserRow[] }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_assignment_users",
	);
}

export function createPortalTicket(args: {
	subject: string;
	description?: string;
	priority?: string;
	customer?: string;
	ticket_type: string;
	/** Internal team only: `'Internal'` for test / internal-only tickets (no customer). */
	work_scope?: "Customer" | "Internal";
}) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockCreatePortalTicket(args));
	}
	return callMethod<{
		name: string;
		subject: string;
		status: string;
		customer: string;
		work_scope?: string;
	}>("printechs_support.printechs_support_system.api.portal_api.create_portal_ticket", args);
}

export function createPortalSupportTask(args: {
	/** Omit or empty for internal-only task (internal users only; requires division). */
	support_ticket?: string;
	subject: string;
	task_type?: string;
	due_date?: string | null;
	/** Required when support_ticket is empty (Software, Industrial, Retail). */
	division?: string;
	/** Optional plain text or HTML (server sanitizes). */
	description?: string;
	/** Printechs (default) or Customer — who must act on this task. */
	responsible_side?: "Printechs" | "Customer";
}) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockCreatePortalSupportTask(args));
	}
	const payload: Record<string, unknown> = {
		subject: args.subject,
		task_type: args.task_type ?? "",
		due_date: args.due_date ?? "",
		description: args.description?.trim() ?? "",
		responsible_side: args.responsible_side ?? "Printechs",
	};
	const st = (args.support_ticket ?? "").trim();
	if (st) {
		payload.support_ticket = st;
	} else {
		// Omit support_ticket entirely so the server treats the task as ticket-less (internal).
		// Sending "" can confuse older benches or proxies.
		payload.division = (args.division ?? "").trim();
	}
	return callMethod<{
		name: string;
		subject: string;
		status: string;
		support_ticket: string | null;
		division?: string | null;
		responsible_side?: string;
		customer?: string | null;
	}>("printechs_support.printechs_support_system.api.portal_api.create_portal_support_task", payload);
}

/** Internal: subject + description. Customers (ticket-linked task): description only. */
export function updatePortalTask(
	taskName: string,
	args: { subject?: string; description?: string },
) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTask(taskName, args));
	}
	const payload: Record<string, unknown> = { task_name: taskName.trim() };
	if (args.subject !== undefined) {
		payload.subject = args.subject;
	}
	if (args.description !== undefined) {
		payload.description = args.description;
	}
	return callMethod<{ ok: boolean; name: string; subject: string; status: string }>(
		"printechs_support.printechs_support_system.api.portal_api.update_portal_task",
		payload,
	);
}

export function updatePortalTicketAssignment(
	ticketName: string,
	args: { team?: string; assignees?: string | string[] },
) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTicketAssignment(ticketName, args));
	}
	const payload: Record<string, unknown> = { ticket_name: ticketName };
	if (args.team !== undefined) {
		payload.team = args.team;
	}
	if (args.assignees !== undefined) {
		payload.assignees =
			typeof args.assignees === "string" ? args.assignees : JSON.stringify(args.assignees);
	}
	return callMethod<{
		ok: boolean;
		team: string;
		assigned_to: string;
		assigned_users: string[];
		status: string;
	}>("printechs_support.printechs_support_system.api.portal_api.update_portal_ticket_assignment", payload);
}

export function updatePortalTaskAssignment(taskName: string, assignees: string | string[]) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTaskAssignment(taskName, assignees));
	}
	const a = typeof assignees === "string" ? assignees : JSON.stringify(assignees);
	return callMethod<{
		ok: boolean;
		assigned_to_user: string;
		assigned_users: string[];
	}>("printechs_support.printechs_support_system.api.portal_api.update_portal_task_assignment", {
		task_name: taskName,
		assignees: a,
	});
}

export function portalTaskPath(name: string): string {
	return `/tasks/${encodeURIComponent(name)}`;
}

export function portalTaskNewPath(ticketName?: string): string {
	const q = ticketName?.trim() ? `?ticket=${encodeURIComponent(ticketName.trim())}` : "";
	return `/tasks/new${q}`;
}

export function getPortalTicket(name: string) {
	if (isPortalMockDataEnabled()) {
		return Promise.resolve(mockPortalTicket(name));
	}
	return callMethod<Record<string, unknown>>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket",
		{ name },
	);
}

export function getPortalTask(name: string) {
	if (isPortalMockDataEnabled()) {
		return Promise.resolve(mockPortalTask(name));
	}
	return callMethod<Record<string, unknown>>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_task",
		{ name },
	);
}

/**
 * URL for the Frappe website login page.
 * Same-origin: sets redirect-to back to the current portal path.
 * Cross-origin: Frappe cannot safely redirect to another hostname after login; opens ERP login with redirect home (see .env.example).
 */
export function loginUrl(redirectTarget?: string): string {
	const frappeOrigin = getFrappeSiteOrigin();
	const u = new URL("/login", frappeOrigin);
	if (frappeOrigin === window.location.origin) {
		const target =
			redirectTarget ?? `${window.location.pathname}${window.location.search}${window.location.hash}`;
		u.searchParams.set("redirect-to", target.startsWith("/") ? target : `/${target}`);
		return u.pathname + u.search;
	}
	u.searchParams.set("redirect-to", "/");
	return u.toString();
}

/**
 * Frappe `cmd` logout that redirects to `/support-portal` after session ends (not `web_logout`, which stays on a generic “Logged out” page).
 */
export function logoutUrl(): string {
	const frappeOrigin = getFrappeSiteOrigin();
	const u = new URL("/", frappeOrigin);
	u.searchParams.set("cmd", "printechs_support.printechs_support_system.api.portal_api.portal_web_logout");
	if (typeof window !== "undefined" && frappeOrigin === window.location.origin) {
		return `${u.pathname}${u.search}`;
	}
	return u.toString();
}

/* —— Comments, status, files (portal) —— */

async function callMultipart<T>(method: string, formData: FormData): Promise<T> {
	const csrf = await resolveCsrfToken();
	const res = await fetch(apiUrl(`/api/method/${encodeURIComponent(method)}`), {
		method: "POST",
		credentials: "include",
		headers: {
			Accept: "application/json",
			"X-Frappe-CSRF-Token": csrf,
		},
		body: formData,
	});
	let data: { message?: T; exc?: string };
	try {
		data = (await res.json()) as { message?: T; exc?: string };
	} catch {
		throw new Error(`HTTP ${res.status}: invalid response`);
	}
	if (!res.ok) {
		const raw = (data as { exc?: string }).exc || (data as { message?: string }).message || `HTTP ${res.status}`;
		throw new Error(typeof raw === "string" ? sanitizeExc(String(raw)) : String(raw));
	}
	if (data.exc) {
		throw new Error(sanitizeExc(data.exc));
	}
	return data.message as T;
}

export function getPortalTicketComments(ticketName: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTicketComments(ticketName));
	}
	return callMethod<PortalComment[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_comments",
		{ ticket_name: ticketName },
	);
}

export function getPortalTaskComments(taskName: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTaskComments(taskName));
	}
	return callMethod<PortalComment[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_task_comments",
		{ task_name: taskName },
	);
}

export type PortalDeskHistoryChange = { fieldname: string; label: string; old: string; new: string };

export type PortalDeskHistoryEntry = {
	name: string;
	at: string | null;
	user: string;
	user_full_name: string;
	changes: PortalDeskHistoryChange[];
	impersonated_by?: string;
};

/** Internal users: Frappe Version history (Desk form saves), same source as ticket → Menu → Versions. */
export function getPortalTicketDeskHistory(ticketName: string, limit = 50) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTicketDeskHistory());
	}
	return callMethod<{ entries: PortalDeskHistoryEntry[] }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_desk_history",
		{ ticket_name: ticketName, limit },
	);
}

export type PortalAddCommentResult = {
	ok: boolean;
	ticket_status?: string;
	task_status?: string;
};

export function addPortalTicketComment(
	ticketName: string,
	content: string,
	isInternalNote = false,
	inReplyTo?: string | null,
	attachmentFileName?: string | null,
	setStatus?: string | null,
	opts?: {
		/** Waiting on customer: omit or ``provide_information`` hands ticket back to support; ``acknowledgement_only`` keeps Waiting for Customer. */
		reply_mode?: "provide_information" | "acknowledgement_only";
		/** Internal user, customer-visible reply: smart workflow (ignored if ``set_status`` is sent). */
		technician_reply_effect?: "normal_reply" | "expect_customer_response";
	},
) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) =>
			m.mockAddPortalTicketComment(ticketName, content, isInternalNote, inReplyTo, attachmentFileName, setStatus),
		);
	}
	const args: Record<string, unknown> = {
		ticket_name: ticketName,
		content,
		is_internal_note: isInternalNote ? 1 : 0,
	};
	const tid = (inReplyTo ?? "").trim();
	if (tid) {
		args.in_reply_to = tid;
	}
	const att = (attachmentFileName ?? "").trim();
	if (att) {
		args.attachment = att;
	}
	const st = (setStatus ?? "").trim();
	if (st) {
		args.set_status = st;
	}
	const rm = opts?.reply_mode;
	if (rm) {
		args.reply_mode = rm;
	}
	const tre = opts?.technician_reply_effect;
	if (tre) {
		args.technician_reply_effect = tre;
	}
	return callMethod<PortalAddCommentResult>(
		"printechs_support.printechs_support_system.api.portal_api.add_portal_ticket_comment",
		args,
	);
}

export function addPortalTaskComment(
	taskName: string,
	content: string,
	isInternalNote = false,
	inReplyTo?: string | null,
	attachmentFileName?: string | null,
	setStatus?: string | null,
) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) =>
			m.mockAddPortalTaskComment(taskName, content, isInternalNote, inReplyTo, attachmentFileName, setStatus),
		);
	}
	const args: Record<string, unknown> = {
		task_name: taskName,
		content,
		is_internal_note: isInternalNote ? 1 : 0,
	};
	const tid = (inReplyTo ?? "").trim();
	if (tid) {
		args.in_reply_to = tid;
	}
	const att = (attachmentFileName ?? "").trim();
	if (att) {
		args.attachment = att;
	}
	const st = (setStatus ?? "").trim();
	if (st) {
		args.set_status = st;
	}
	return callMethod<PortalAddCommentResult>(
		"printechs_support.printechs_support_system.api.portal_api.add_portal_task_comment",
		args,
	);
}

/** Update ticket subject / description / priority (internal); customers may pass ``description`` only. */
export function updatePortalTicket(
	ticketName: string,
	fields: { subject?: string; description?: string; priority?: string },
) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTicket(ticketName, fields));
	}
	const args: Record<string, unknown> = { ticket_name: ticketName };
	if (fields.subject !== undefined) {
		args.subject = fields.subject;
	}
	if (fields.description !== undefined) {
		args.description = fields.description;
	}
	if (fields.priority !== undefined) {
		args.priority = fields.priority;
	}
	return callMethod<{
		ok: boolean;
		name: string;
		subject: string;
		status: string;
		priority: string;
	}>("printechs_support.printechs_support_system.api.portal_api.update_portal_ticket", args);
}

export function updatePortalTicketStatus(ticketName: string, status: string, confirmationComment?: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTicketStatus(ticketName, status, confirmationComment));
	}
	const args: Record<string, unknown> = { ticket_name: ticketName, status };
	if (confirmationComment != null) {
		args.confirmation_comment = confirmationComment;
	}
	return callMethod<{ ok: boolean; status: string }>(
		"printechs_support.printechs_support_system.api.portal_api.update_portal_ticket_status",
		args,
	);
}

export function updatePortalTaskStatus(taskName: string, status: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTaskStatus(taskName, status));
	}
	return callMethod<{ ok: boolean; status: string }>(
		"printechs_support.printechs_support_system.api.portal_api.update_portal_task_status",
		{ task_name: taskName, status },
	);
}

/** Internal users: set task due date (omit or pass empty string to clear). */
export function updatePortalTaskDueDate(taskName: string, dueDate: string | null) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTaskDueDate(taskName, dueDate));
	}
	return callMethod<{ ok: boolean; due_date: string | null; due_date_calendar?: string | null }>(
		"printechs_support.printechs_support_system.api.portal_api.update_portal_task_due_date",
		{ task_name: taskName, due_date: dueDate ?? "" },
	);
}

/** Internal / assignees: set ticket due date; syncs to all tasks. Empty string clears. */
export function updatePortalTicketDueDate(ticketName: string, dueDate: string | null) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUpdatePortalTicketDueDate(ticketName, dueDate));
	}
	return callMethod<{ ok: boolean; due_date: string | null; due_date_calendar?: string | null }>(
		"printechs_support.printechs_support_system.api.portal_api.update_portal_ticket_due_date",
		{ ticket_name: ticketName, due_date: dueDate ?? "" },
	);
}

export function getPortalTicketFiles(ticketName: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTicketFiles(ticketName));
	}
	return callMethod<PortalFileRow[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_files",
		{ ticket_name: ticketName },
	);
}

export function getPortalTaskFiles(taskName: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTaskFiles(taskName));
	}
	return callMethod<PortalFileRow[]>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_task_files",
		{ task_name: taskName },
	);
}

export async function uploadPortalTicketFile(ticketName: string, file: File) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUploadPortalTicketFile(ticketName, file));
	}
	const fd = new FormData();
	fd.append("file", file);
	fd.append("ticket_name", ticketName);
	return callMultipart<{ ok: boolean; name: string; file_name: string; file_url: string }>(
		"printechs_support.printechs_support_system.api.portal_api.portal_upload_ticket_file",
		fd,
	);
}

export async function uploadPortalTaskFile(taskName: string, file: File) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockUploadPortalTaskFile(taskName, file));
	}
	const fd = new FormData();
	fd.append("file", file);
	fd.append("task_name", taskName);
	return callMultipart<{ ok: boolean; name: string; file_name: string; file_url: string }>(
		"printechs_support.printechs_support_system.api.portal_api.portal_upload_task_file",
		fd,
	);
}

export function getPortalTicketStatusOptions(ticketName?: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTicketStatusOptions(ticketName));
	}
	const args: Record<string, unknown> = {};
	const tn = (ticketName ?? "").trim();
	if (tn) {
		args.ticket_name = tn;
	}
	return callMethod<{ options: string[] }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_status_options",
		args,
	);
}

export function markTicketAwaitingCustomerResolution(ticketName: string, hours = 24) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockMarkTicketAwaitingCustomerResolution(ticketName, hours));
	}
	return callMethod<{ ok: boolean; customer_resolution_deadline: string }>(
		"printechs_support.printechs_support_system.api.portal_api.mark_ticket_awaiting_customer_resolution",
		{ ticket_name: ticketName, hours },
	);
}

export function reopenPortalTicket(ticketName: string, message: string) {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockReopenPortalTicket(ticketName, message));
	}
	return callMethod<{ ok: boolean; status: string }>(
		"printechs_support.printechs_support_system.api.portal_api.portal_ticket_workflow_action",
		{ action: "customer_reopen", ticket_name: ticketName, message },
	);
}

export function getPortalTaskStatusOptions() {
	if (isPortalMockDataEnabled()) {
		return import("./portalMock").then((m) => m.mockGetPortalTaskStatusOptions());
	}
	return callMethod<{ options: string[] }>(
		"printechs_support.printechs_support_system.api.portal_api.get_portal_task_status_options",
	);
}
