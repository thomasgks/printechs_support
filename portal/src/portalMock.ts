/**
 * Demo fixtures for local UI / layout checks. Enable with VITE_PORTAL_USE_MOCK_DATA=true
 * Disable (or unset) for real bench data; you can delete this file when no longer needed.
 */

import type { PortalBootstrapResult } from "./api";
import type { CalendarEventItem } from "./calendarUtils";
import type { PortalTaskSort } from "./lib/taskSort";
import { sortPortalTasks } from "./lib/taskSort";
import type { PortalComment, PortalFileRow } from "./types/portal";

const MOCK_SESSION_KEY = "printechs_portal_mock";

/**
 * Reads `?mock=1` or `?portal_mock=1` (and `=0` to clear) so mock works when the bundle was built
 * without `VITE_PORTAL_USE_MOCK_DATA` — e.g. portal opened from Frappe `/support-portal/`.
 */
function syncMockFlagFromUrl(): void {
	if (typeof window === "undefined") {
		return;
	}
	try {
		const q = new URLSearchParams(window.location.search);
		const on = q.get("mock") === "1" || q.get("portal_mock") === "1";
		const off = q.get("mock") === "0" || q.get("portal_mock") === "0";
		if (on) {
			sessionStorage.setItem(MOCK_SESSION_KEY, "1");
		}
		if (off) {
			sessionStorage.removeItem(MOCK_SESSION_KEY);
		}
	} catch {
		/* private mode / blocked storage */
	}
}

function envSaysMock(): boolean {
	const v = import.meta.env.VITE_PORTAL_USE_MOCK_DATA;
	if (v == null || v === "") {
		return false;
	}
	const s = String(v).trim().toLowerCase();
	return s === "true" || s === "1" || s === "yes";
}

/** When .env sets mock off, clear tab session from an older ?mock=1 visit. */
function envExplicitlyDisablesMock(): boolean {
	const v = import.meta.env.VITE_PORTAL_USE_MOCK_DATA;
	if (v == null || v === "") {
		return false;
	}
	const s = String(v).trim().toLowerCase();
	return s === "false" || s === "0" || s === "no" || s === "off";
}

function clearMockSessionFlag(): void {
	if (typeof window === "undefined") {
		return;
	}
	try {
		sessionStorage.removeItem(MOCK_SESSION_KEY);
	} catch {
		/* ignore */
	}
}

export function isPortalMockDataEnabled(): boolean {
	syncMockFlagFromUrl();

	/* Build must be recreated after changing VITE_* — but this fixes stale ?mock=1 sessionStorage. */
	if (envExplicitlyDisablesMock()) {
		clearMockSessionFlag();
		return false;
	}

	if (envSaysMock()) {
		return true;
	}
	try {
		if (typeof window !== "undefined" && sessionStorage.getItem(MOCK_SESSION_KEY) === "1") {
			return true;
		}
	} catch {
		/* ignore */
	}
	return false;
}

export const MOCK_PORTAL_BOOTSTRAP: Extract<PortalBootstrapResult, { logged_in: true }> = {
	logged_in: true,
	user: "demo.user@example.com",
	full_name: "Alex Demo (mock)",
	customers: ["Acme Corporation", "Globex Trading Ltd"],
	internal: true,
};

/** Matches get_portal_dashboard_stats */
export const MOCK_DASHBOARD_STATS = {
	pending_tickets: 4,
	overdue_tickets: 1,
	tickets_waiting_customer: 1,
	tickets_waiting_internal: 0,
	pending_tasks: 5,
	overdue_tasks: 2,
	completed_today: 1,
	waiting_customer: 2,
	waiting_internal: 1,
	sla_breached: 2,
	delayed_flagged: 1,
	tickets_by_status: {
		Open: 2,
		Draft: 1,
		"In Progress": 1,
		"Waiting for Customer": 1,
		Resolved: 2,
		Closed: 3,
	},
	tasks_by_status: {
		Open: 2,
		"In Progress": 2,
		"Waiting for Customer": 1,
		"Waiting for Printechs": 1,
		Completed: 3,
		Delayed: 0,
	},
	assignee_load: [
		{ name: "Administrator", count: 3 },
		{ name: "Unassigned", count: 2 },
	],
	monthly_completion: [
		{ month: "2026-01", label: "Jan 2026", count: 2 },
		{ month: "2026-02", label: "Feb 2026", count: 4 },
		{ month: "2026-03", label: "Mar 2026", count: 3 },
		{ month: "2026-04", label: "Apr 2026", count: 5 },
		{ month: "2026-05", label: "May 2026", count: 0 },
		{ month: "2026-06", label: "Jun 2026", count: 0 },
	],
};

/** Matches get_portal_tickets (client-side filter for mock). */
export function mockGetPortalTickets(
	limit: number,
	opts?: { search?: string; activeOnly?: boolean; customer?: string; ticketType?: string },
): Record<string, unknown>[] {
	let rows = [...MOCK_PORTAL_TICKETS];
	if (opts?.activeOnly === true) {
		rows = rows.filter((r) => !["Resolved", "Closed", "Cancelled"].includes(String(r.status ?? "")));
	}
	const customer = (opts?.customer ?? "").trim();
	if (customer) {
		const customerText = customer.toLowerCase();
		rows = rows.filter((r) => String(r.customer ?? "").toLowerCase().includes(customerText));
	}
	const ticketType = (opts?.ticketType ?? "").trim();
	if (ticketType) {
		rows = rows.filter((r) => String(r.ticket_type ?? "") === ticketType);
	}
	const q = (opts?.search ?? "").trim().toLowerCase();
	if (q) {
		rows = rows.filter((r) => String(r.name ?? "").toLowerCase().includes(q));
	}
	return rows.slice(0, Math.min(limit, rows.length));
}

/** Matches get_portal_tickets fields */
export const MOCK_PORTAL_TICKETS: Record<string, unknown>[] = [
	{
		name: "SUPP-MOCK-0001",
		subject: "Printer offline — warehouse line 2",
		status: "Open",
		priority: "High",
		ticket_type: "General",
		ticket_type_label: "General",
		modified: "2026-04-05 14:22:00.000000",
		customer: "Acme Corporation",
	},
	{
		name: "SUPP-MOCK-0002",
		subject: "Toner reorder approval",
		status: "In Progress",
		priority: "Medium",
		ticket_type: "General",
		ticket_type_label: "General",
		modified: "2026-04-04 09:10:00.000000",
		customer: "Acme Corporation",
	},
	{
		name: "SUPP-MOCK-0003",
		subject: "Annual service contract renewal",
		status: "Closed",
		priority: "Low",
		ticket_type: "Question",
		ticket_type_label: "Question",
		modified: "2026-03-28 16:45:00.000000",
		customer: "Globex Trading Ltd",
	},
];

/** Matches get_portal_tasks fields */
export const MOCK_PORTAL_TASKS: Record<string, unknown>[] = [
	{
		name: "TASK-MOCK-101",
		subject: "Replace fuser unit",
		support_ticket: "SUPP-MOCK-0001",
		status: "In Progress",
		task_type: "Repair",
		modified: "2026-04-05 11:00:00.000000",
		customer: "Acme Corporation",
		assigned_to_user: "Administrator",
		assigned_users: ["Administrator", "lead.engineer@example.com"],
		due_date: "2026-04-10 18:00:00",
		delay_owner: "Printechs",
		delay_reason: null,
		is_delayed: 0,
		delay_days: null,
		creation: "2026-04-01 09:00:00",
	},
	{
		name: "TASK-MOCK-102",
		subject: "Verify network scan to SMB share",
		support_ticket: "SUPP-MOCK-0001",
		status: "Open",
		task_type: "Follow-up",
		modified: "2026-04-05 08:30:00.000000",
		customer: "Acme Corporation",
		assigned_to_user: null,
		assigned_users: [],
		due_date: "2026-04-02 12:00:00",
		delay_owner: "Customer",
		delay_reason: null,
		is_delayed: 1,
		delay_days: 3,
		creation: "2026-03-28 08:00:00",
	},
	{
		name: "TASK-MOCK-103",
		subject: "Send signed renewal PDF",
		support_ticket: "SUPP-MOCK-0003",
		status: "Completed",
		task_type: "Admin",
		modified: "2026-03-29 10:15:00.000000",
		customer: "Globex Trading Ltd",
		assigned_to_user: "Administrator",
		assigned_users: ["Administrator"],
		due_date: null,
		delay_owner: "",
		delay_reason: null,
		is_delayed: 0,
		delay_days: null,
		creation: "2026-03-20 10:00:00",
	},
];

function calendarFromDueString(d: string | null): string | null {
	if (!d || d.trim() === "") return null;
	const s = d.trim();
	return s.length >= 10 && s[4] === "-" && s[7] === "-" ? s.slice(0, 10) : null;
}

/** Matches get_portal_ticket / get_portal_task single-doc payloads (mock). */
export function mockPortalTicket(name: string): Record<string, unknown> {
	const row = MOCK_PORTAL_TICKETS.find((t) => String(t.name) === name);
	if (row) {
		const st = String(row.status ?? "");
		const terminal = ["Resolved", "Closed", "Cancelled"].includes(st);
		return {
			name: row.name,
			subject: row.subject,
			status: row.status,
			priority: row.priority,
			ticket_type: "General",
			ticket_type_label: "General",
			team: "",
			division: "Software",
			customer: row.customer,
			customer_name: String(row.customer ?? ""),
			assigned_to: "Administrator",
			assigned_users: ["Administrator"],
			modified: row.modified,
			opening_date: "2026-04-01 09:00:00",
			due_date: null,
			due_date_calendar: null,
			description:
				"This is mock content shown only when VITE_PORTAL_USE_MOCK_DATA is on. With mock off, details load from your site.",
			can_edit_ticket_schedule: true,
			resolved_on: terminal ? String(row.modified) : null,
			closed_on: st === "Closed" ? String(row.modified) : null,
			resolution_type: terminal ? "Enhancement Logged" : "",
			resolution_summary_html: terminal
				? "<p>Mock resolution summary. Reopen the ticket in Desk to post again.</p>"
				: "",
			communication_locked: terminal,
			root_cause: "Mock root cause (internal)",
		};
	}
	return {
		name,
		subject: "Unknown ticket (mock)",
		status: "Open",
		priority: "—",
		ticket_type: "",
		ticket_type_label: "",
		team: "",
		division: "",
		customer: "",
		customer_name: "",
		assigned_to: "",
		assigned_users: [],
		modified: null,
		opening_date: null,
		due_date: null,
		due_date_calendar: null,
		description: "This ticket id is not in the mock list.",
		can_edit_ticket_schedule: true,
		resolved_on: null,
		closed_on: null,
		resolution_type: "",
		resolution_summary_html: "",
		communication_locked: false,
	};
}

export function mockPortalTask(name: string): Record<string, unknown> {
	const row = MOCK_PORTAL_TASKS.find((t) => String(t.name) === name);
	if (row) {
		return {
			name: row.name,
			subject: row.subject,
			status: row.status,
			task_type: row.task_type,
			support_ticket: row.support_ticket,
			ticket_subject: "Linked ticket (mock)",
			customer: row.customer ?? "Acme Corporation",
			division: "Software",
			project: "",
			responsible_side: "Printechs",
			assigned_to_user: row.assigned_to_user ?? "",
			assigned_users: (row.assigned_users as string[] | undefined) ?? [],
			predecessor_task: "",
			modified: row.modified,
			creation: row.creation ?? "2026-04-01 09:00:00",
			due_date: row.due_date ?? null,
			due_date_calendar: calendarFromDueString((row.due_date as string | null | undefined) ?? null),
			planned_start_date: null,
			planned_end_date: null,
			actual_start_date: null,
			actual_end_date: null,
			is_delayed: row.is_delayed ?? 0,
			delay_owner: row.delay_owner ?? "",
			delay_reason: row.delay_reason ?? "",
			delay_remarks: "",
			delay_days: row.delay_days ?? null,
			description:
				"This is mock content. With mock off, task details load from your site API.",
			can_edit_task_schedule: true,
		};
	}
	return {
		name,
		subject: "Unknown task (mock)",
		status: "Open",
		task_type: "",
		support_ticket: "",
		ticket_subject: "",
		customer: "",
		division: "",
		project: "",
		responsible_side: "",
		assigned_to_user: "",
		assigned_users: [],
		predecessor_task: "",
		modified: null,
		creation: null,
		due_date: null,
		due_date_calendar: null,
		planned_start_date: null,
		planned_end_date: null,
		actual_start_date: null,
		actual_end_date: null,
		is_delayed: 0,
		delay_owner: "",
		delay_reason: "",
		delay_remarks: "",
		delay_days: null,
		description: "This task id is not in the mock list.",
		can_edit_task_schedule: true,
	};
}

/** Mutable mock thread (comments live on Support Ticket). */
export const MOCK_TICKET_COMMENTS: Record<string, PortalComment[]> = {
	"SUPP-MOCK-0001": [
		{
			name: "cmt-1",
			comment_type: "Customer Reply",
			comment_by: "demo.user@example.com",
			author_name: "Alex Demo (mock)",
			comment_on: "2026-04-05 10:15:00",
			is_customer_visible: 1,
			content: "<p>Thanks — we will validate the firmware tonight.</p>",
			internal_only: false,
		},
		{
			name: "cmt-int",
			comment_type: "Internal Note",
			comment_by: "Administrator",
			author_name: "Support Team",
			comment_on: "2026-04-05 09:00:00",
			is_customer_visible: 0,
			content: "<p>Internal: customer confirmed network path.</p>",
			internal_only: true,
		},
		{
			name: "cmt-2",
			comment_type: "System Update",
			comment_by: "Administrator",
			author_name: "Administrator",
			comment_on: "2026-04-05 10:22:00",
			is_customer_visible: 1,
			content: "<p><strong>Status</strong> updated from <em>Open</em> to <em>In Progress</em></p>",
			internal_only: false,
		},
	],
};

export const MOCK_TICKET_FILES: Record<string, PortalFileRow[]> = {
	"SUPP-MOCK-0001": [
		{
			name: "FILE-MOCK-1",
			file_name: "network-diagram.png",
			file_url: "#mock-file",
			file_size: 128000,
			creation: "2026-04-04 12:00:00",
			owner: "demo.user@example.com",
		},
	],
};

export const MOCK_TASK_FILES: Record<string, PortalFileRow[]> = {
	"TASK-MOCK-101": [
		{
			name: "FILE-MOCK-T1",
			file_name: "fuser-photo.jpg",
			file_url: "#mock-task-file",
			file_size: 890000,
			creation: "2026-04-05 09:30:00",
			owner: "Administrator",
		},
	],
};

function mockEscape(s: string): string {
	return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function mockGetPortalTicketComments(ticketName: string): Promise<PortalComment[]> {
	const rows = MOCK_TICKET_COMMENTS[ticketName] ?? [];
	if (MOCK_PORTAL_BOOTSTRAP.internal) {
		return Promise.resolve([...rows]);
	}
	return Promise.resolve(rows.filter((r) => r.is_customer_visible === 1));
}

export function mockGetPortalTicketDeskHistory(): Promise<{ entries: [] }> {
	return Promise.resolve({ entries: [] });
}

export function mockAddPortalTicketComment(
	ticketName: string,
	content: string,
	isInternalNote: boolean,
	inReplyTo?: string | null,
	attachmentFileName?: string | null,
	setStatus?: string | null,
): Promise<{ ok: boolean; ticket_status?: string }> {
	if (!MOCK_TICKET_COMMENTS[ticketName]) {
		MOCK_TICKET_COMMENTS[ticketName] = [];
	}
	const u = MOCK_PORTAL_BOOTSTRAP.user;
	const vis = isInternalNote ? 0 : 1;
	const trimmed = (inReplyTo || "").trim();
	const att = (attachmentFileName || "").trim();
	const body =
		content && content.trim()
			? content
			: att
				? "<p>Shared an attachment.</p>"
				: "<p></p>";
	MOCK_TICKET_COMMENTS[ticketName].push({
		name: `mock-${Date.now()}`,
		comment_type: isInternalNote ? "Internal Note" : "Customer Reply",
		comment_by: u,
		author_name: MOCK_PORTAL_BOOTSTRAP.full_name,
		comment_on: new Date().toISOString().slice(0, 19).replace("T", " "),
		is_customer_visible: vis,
		content: body,
		internal_only: isInternalNote,
		...(trimmed ? { in_reply_to: trimmed } : {}),
		...(att ? { attachment: att, attachment_url: "https://placehold.co/320x200/png?text=Image" } : {}),
	});
	const st = (setStatus || "").trim();
	const row = MOCK_PORTAL_TICKETS.find((t) => String(t.name) === ticketName);
	if (st && MOCK_PORTAL_BOOTSTRAP.internal && row && typeof row === "object") {
		(row as { status?: string }).status = st;
	}
	const ticket_status =
		row && typeof row === "object" ? String((row as { status?: string }).status ?? "") : "";
	return Promise.resolve({ ok: true, ticket_status });
}

const MOCK_TASK_COMMENTS: Record<string, PortalComment[]> = {};

export function mockGetPortalTaskComments(taskName: string): Promise<PortalComment[]> {
	const rows = MOCK_TASK_COMMENTS[taskName] ?? [];
	if (MOCK_PORTAL_BOOTSTRAP.internal) {
		return Promise.resolve([...rows]);
	}
	return Promise.resolve(rows.filter((r) => r.is_customer_visible === 1));
}

export function mockAddPortalTaskComment(
	taskName: string,
	content: string,
	isInternalNote: boolean,
	inReplyTo?: string | null,
	attachmentFileName?: string | null,
	setStatus?: string | null,
): Promise<{ ok: boolean; task_status?: string }> {
	if (!MOCK_TASK_COMMENTS[taskName]) {
		MOCK_TASK_COMMENTS[taskName] = [];
	}
	const u = MOCK_PORTAL_BOOTSTRAP.user;
	const vis = isInternalNote ? 0 : 1;
	const trimmed = (inReplyTo || "").trim();
	const att = (attachmentFileName || "").trim();
	const body =
		content && content.trim()
			? content
			: att
				? "<p>Shared an attachment.</p>"
				: "<p></p>";
	MOCK_TASK_COMMENTS[taskName].push({
		name: `mock-task-${Date.now()}`,
		comment_type: isInternalNote ? "Internal Note" : "Customer Reply",
		comment_by: u,
		author_name: MOCK_PORTAL_BOOTSTRAP.full_name,
		comment_on: new Date().toISOString().slice(0, 19).replace("T", " "),
		is_customer_visible: vis,
		content: body,
		internal_only: isInternalNote,
		...(trimmed ? { in_reply_to: trimmed } : {}),
		...(att ? { attachment: att, attachment_url: "https://placehold.co/320x200/png?text=Image" } : {}),
	});
	const st = (setStatus || "").trim();
	const row = MOCK_PORTAL_TASKS.find((t) => String(t.name) === taskName);
	if (st && MOCK_PORTAL_BOOTSTRAP.internal && row && typeof row === "object") {
		(row as { status?: string }).status = st;
	}
	const task_status =
		row && typeof row === "object" ? String((row as { status?: string }).status ?? "") : "";
	return Promise.resolve({ ok: true, task_status });
}

export function mockUpdatePortalTicket(
	ticketName: string,
	fields: { subject?: string; description?: string; priority?: string },
): Promise<{ ok: boolean; name: string; subject: string; status: string; priority: string }> {
	const row = MOCK_PORTAL_TICKETS.find((t) => String(t.name) === ticketName);
	const subject = fields.subject ?? row?.subject ?? "(mock ticket)";
	const priority = fields.priority ?? row?.priority ?? "Medium";
	if (row) {
		if (fields.subject !== undefined) {
			(row as { subject?: string }).subject = subject;
		}
		if (fields.description !== undefined) {
			(row as { description?: string }).description = fields.description;
		}
		if (fields.priority !== undefined) {
			(row as { priority?: string }).priority = priority;
		}
	}
	return Promise.resolve({
		ok: true,
		name: ticketName,
		subject,
		status: (row as { status?: string } | undefined)?.status ?? "Open",
		priority,
	});
}

export function mockUpdatePortalTicketStatus(
	ticketName: string,
	status: string,
	confirmationComment?: string,
): Promise<{ ok: boolean; status: string }> {
	const row = MOCK_PORTAL_TICKETS.find((t) => String(t.name) === ticketName);
	if (row) {
		(row as { status?: string }).status = status;
	}
	void confirmationComment;
	return Promise.resolve({ ok: true, status });
}

export function mockUpdatePortalTaskStatus(taskName: string, status: string): Promise<{ ok: boolean; status: string }> {
	const row = MOCK_PORTAL_TASKS.find((t) => String(t.name) === taskName);
	if (row) {
		(row as { status?: string }).status = status;
	}
	return Promise.resolve({ ok: true, status });
}

export function mockUpdatePortalTaskDueDate(
	taskName: string,
	dueDate: string | null,
): Promise<{ ok: boolean; due_date: string | null; due_date_calendar: string | null }> {
	const row = MOCK_PORTAL_TASKS.find((t) => String(t.name) === taskName);
	const v = dueDate && dueDate.trim() !== "" ? dueDate : null;
	if (row) {
		(row as { due_date?: string | null }).due_date = v;
	}
	return Promise.resolve({ ok: true, due_date: v, due_date_calendar: calendarFromDueString(v) });
}

export function mockUpdatePortalTicketDueDate(
	ticketName: string,
	dueDate: string | null,
): Promise<{ ok: boolean; due_date: string | null; due_date_calendar: string | null }> {
	const row = MOCK_PORTAL_TICKETS.find((t) => String(t.name) === ticketName);
	const v = dueDate && dueDate.trim() !== "" ? dueDate : null;
	if (row) {
		(row as { due_date?: string | null }).due_date = v;
	}
	return Promise.resolve({ ok: true, due_date: v, due_date_calendar: calendarFromDueString(v) });
}

export function mockUpdatePortalTask(
	taskName: string,
	args: { subject?: string; description?: string },
): Promise<{ ok: boolean; name: string; subject: string; status: string }> {
	const row = MOCK_PORTAL_TASKS.find((t) => String(t.name) === taskName);
	if (row && args.subject !== undefined) {
		(row as { subject?: string }).subject = args.subject;
	}
	void args.description;
	return Promise.resolve({
		ok: true,
		name: taskName,
		subject: (row?.subject as string) ?? "Mock",
		status: String((row as { status?: string })?.status ?? "Open"),
	});
}

export function mockGetPortalTicketFiles(ticketName: string): Promise<PortalFileRow[]> {
	return Promise.resolve(MOCK_TICKET_FILES[ticketName] ?? []);
}

export function mockGetPortalTaskFiles(taskName: string): Promise<PortalFileRow[]> {
	return Promise.resolve(MOCK_TASK_FILES[taskName] ?? []);
}

export function mockUploadPortalTicketFile(
	ticketName: string,
	file: File,
): Promise<{ ok: boolean; name: string; file_name: string; file_url: string }> {
	if (!MOCK_TICKET_FILES[ticketName]) {
		MOCK_TICKET_FILES[ticketName] = [];
	}
	const row: PortalFileRow = {
		name: `FILE-${Date.now()}`,
		file_name: file.name,
		file_url: "#mock-upload",
		file_size: file.size,
		creation: new Date().toISOString().slice(0, 19).replace("T", " "),
		owner: MOCK_PORTAL_BOOTSTRAP.user,
	};
	MOCK_TICKET_FILES[ticketName].unshift(row);
	return Promise.resolve({ ok: true, name: row.name, file_name: row.file_name, file_url: row.file_url });
}

export function mockUploadPortalTaskFile(
	taskName: string,
	file: File,
): Promise<{ ok: boolean; name: string; file_name: string; file_url: string }> {
	if (!MOCK_TASK_FILES[taskName]) {
		MOCK_TASK_FILES[taskName] = [];
	}
	const row: PortalFileRow = {
		name: `FILE-T-${Date.now()}`,
		file_name: file.name,
		file_url: "#mock-upload-task",
		file_size: file.size,
		creation: new Date().toISOString().slice(0, 19).replace("T", " "),
		owner: MOCK_PORTAL_BOOTSTRAP.user,
	};
	MOCK_TASK_FILES[taskName].unshift(row);
	return Promise.resolve({ ok: true, name: row.name, file_name: row.file_name, file_url: row.file_url });
}

export function mockGetPortalTicketStatusOptions(ticketName?: string): Promise<{ options: string[] }> {
	const full = [
		"Open",
		"Assigned",
		"In Progress",
		"Hold",
		"Waiting for Customer",
		"Waiting for Technician",
		"Reopened",
		"Resolved",
		"Closed",
		"Cancelled",
	];
	if (MOCK_PORTAL_BOOTSTRAP.internal) {
		return Promise.resolve({ options: full });
	}
	const tn = (ticketName ?? "").trim();
	if (!tn) {
		return Promise.resolve({ options: [] });
	}
	/* Customer mock: simulate an open confirmation window so the dropdown can offer Resolved. */
	return Promise.resolve({ options: ["Resolved"] });
}

export function mockMarkTicketAwaitingCustomerResolution(
	ticketName: string,
	hours: number,
): Promise<{ ok: boolean; customer_resolution_deadline: string }> {
	const h = Number.isFinite(hours) && hours > 0 ? hours : 24;
	const d = new Date(Date.now() + h * 3600 * 1000);
	return Promise.resolve({
		ok: true,
		customer_resolution_deadline: d.toISOString().slice(0, 19).replace("T", " "),
	});
}

export function mockReopenPortalTicket(ticketName: string, message: string): Promise<{ ok: boolean; status: string }> {
	const row = MOCK_PORTAL_TICKETS.find((t) => String(t.name) === ticketName);
	if (row) {
		(row as { status?: string }).status = "Reopened";
	}
	void message;
	return Promise.resolve({ ok: true, status: "Reopened" });
}

export function mockGetPortalTaskStatusOptions(): Promise<{ options: string[] }> {
	return Promise.resolve({
		options: ["Open", "In Progress", "Waiting for Customer", "Waiting for Printechs", "Completed", "Cancelled", "Delayed"],
	});
}

export function mockGetPortalTicketCustomers(): Promise<{ customers: { name: string; customer_name: string }[] }> {
	return Promise.resolve({
		customers: [
			{ name: "Acme Corporation", customer_name: "Acme Corporation" },
			{ name: "Globex Trading Ltd", customer_name: "Globex Trading Ltd" },
		],
	});
}

export function mockGetPortalTicketTypes(customer?: string): Promise<{
	types: { name: string; label: string; division: string }[];
	restricted?: boolean;
}> {
	const all = [
		{ name: "General", label: "General", division: "Software" },
		{ name: "Hardware", label: "Hardware", division: "Industrial" },
	];
	const c = (customer ?? "").trim();
	if (c === "Globex Trading Ltd") {
		return Promise.resolve({ types: [{ name: "General", label: "General", division: "Software" }], restricted: true });
	}
	return Promise.resolve({ types: all, restricted: false });
}

export function mockGetPortalTeams(): Promise<{ teams: { name: string; label: string }[] }> {
	return Promise.resolve({
		teams: [
			{ name: "Software-Support", label: "Software Support (Software)" },
			{ name: "Industrial-Support", label: "Industrial Support (Industrial)" },
		],
	});
}

export function mockGetPortalAssignmentUsers(): Promise<{ users: { name: string; full_name: string }[] }> {
	return Promise.resolve({
		users: [
			{ name: "Administrator", full_name: "Administrator" },
			{ name: "user@example.com", full_name: "Demo User" },
		],
	});
}

export function mockCreatePortalTicket(args: {
	subject: string;
	description?: string;
	priority?: string;
	customer?: string;
	ticket_type: string;
	work_scope?: "Customer" | "Internal";
}): Promise<{ name: string; subject: string; status: string; customer: string; work_scope?: string }> {
	void args.ticket_type;
	const n = MOCK_PORTAL_TICKETS.length + 1;
	const name = `SUPP-MOCK-${String(n).padStart(5, "0")}`;
	const internalScope = args.work_scope === "Internal";
	return Promise.resolve({
		name,
		subject: args.subject,
		status: "Open",
		customer: internalScope ? "" : args.customer?.trim() || MOCK_PORTAL_BOOTSTRAP.customers[0] || "Acme Corporation",
		work_scope: internalScope ? "Internal" : "Customer",
	});
}

export function mockCreatePortalSupportTask(args: {
	support_ticket?: string;
	subject: string;
	task_type?: string;
	due_date?: string | null;
	division?: string;
	description?: string;
	responsible_side?: "Printechs" | "Customer";
}): Promise<{
	name: string;
	subject: string;
	status: string;
	support_ticket: string | null;
	division?: string | null;
	responsible_side?: string;
	customer?: string | null;
}> {
	void args.task_type;
	void args.due_date;
	void args.description;
	const tk = (args.support_ticket ?? "").trim();
	const rs = args.responsible_side ?? "Printechs";
	if (!tk) {
		return Promise.resolve({
			name: "SUP-TSK-MOCK-00099",
			subject: args.subject,
			status: "Open",
			support_ticket: null,
			division: (args.division ?? "Software").trim() || "Software",
			responsible_side: rs,
			customer: null,
		});
	}
	return Promise.resolve({
		name: "SUP-TSK-MOCK-00099",
		subject: args.subject,
		status: "Open",
		support_ticket: tk,
		division: null,
		responsible_side: rs,
		customer: MOCK_PORTAL_BOOTSTRAP.customers[0] || "Acme Corporation",
	});
}

/** Matches get_portal_tasks_for_ticket. */
export function mockGetPortalTasksForTicket(
	ticketName: string,
	limit: number,
	sortBy: PortalTaskSort = "task",
): Promise<Record<string, unknown>[]> {
	const q = ticketName.trim();
	let rows = MOCK_PORTAL_TASKS.filter((t) => String(t.support_ticket ?? "") === q);
	rows = rows.slice(0, Math.min(limit, rows.length));
	return Promise.resolve(
		sortPortalTasks(
			rows.map((t) => {
				const d = t.due_date;
				const cal =
					typeof d === "string" && d.length >= 10 && d[4] === "-" && d[7] === "-"
						? d.slice(0, 10)
						: null;
				return { ...t, due_date_calendar: cal };
			}),
			sortBy,
		),
	);
}

export function mockUpdatePortalTicketAssignment(
	_ticketName: string,
	_args: { team?: string; assignees?: string | string[] },
): Promise<{
	ok: boolean;
	team: string;
	assigned_to: string;
	assigned_users: string[];
	status: string;
}> {
	return Promise.resolve({
		ok: true,
		team: _args.team ?? "",
		assigned_to: "Administrator",
		assigned_users: ["Administrator"],
		status: "Assigned",
	});
}

export function mockUpdatePortalTaskAssignment(
	_taskName: string,
	_assignees: string | string[],
): Promise<{ ok: boolean; assigned_to_user: string; assigned_users: string[] }> {
	void _taskName;
	void _assignees;
	return Promise.resolve({
		ok: true,
		assigned_to_user: "Administrator",
		assigned_users: ["Administrator"],
	});
}

/** Sample schedule: timed blocks for day/week grid + all-day row (April 2026 in mock). */
export const MOCK_CALENDAR_EVENTS: CalendarEventItem[] = [
	{ date: "2026-04-01", title: "Content calendar Q2 (all-day)", ticket: "SUPP-MOCK-0001", color: "blue" },
	{ date: "2026-04-07", title: "Quarterly maintenance window", ticket: "SUPP-MOCK-0001", start: "08:00", end: "09:00", color: "slate" },
	{ date: "2026-04-08", title: "Team huddle", ticket: "SUPP-MOCK-0001", start: "09:30", end: "10:00", color: "orange" },
	{ date: "2026-04-08", title: "Budget planning", ticket: "SUPP-MOCK-0002", start: "10:30", end: "12:00", color: "purple" },
	{ date: "2026-04-08", title: "On-site visit — Acme", ticket: "SUPP-MOCK-0001", start: "13:00", end: "15:30", color: "green" },
	{ date: "2026-04-09", title: "Marketing trends sync", ticket: "SUPP-MOCK-0002", start: "11:00", end: "11:45", color: "rose" },
	{ date: "2026-04-09", title: "UI/UX review", ticket: "SUPP-MOCK-0001", start: "14:00", end: "15:00", color: "orange" },
	{ date: "2026-04-10", title: "Remote diagnostics", ticket: "SUPP-MOCK-0001", start: "09:00", end: "10:30", color: "blue" },
	{ date: "2026-04-10", title: "Budget discussion", ticket: "SUPP-MOCK-0003", start: "16:00", end: "17:00", color: "purple" },
	{ date: "2026-04-12", title: "Contract review call", ticket: "SUPP-MOCK-0003", start: "10:00", end: "11:00", color: "green" },
	{ date: "2026-04-15", title: "Toner delivery follow-up", ticket: "SUPP-MOCK-0002", start: "08:30", end: "09:15", color: "slate" },
	{ date: "2026-04-18", title: "Firmware update (evening)", ticket: "SUPP-MOCK-0001", start: "17:30", end: "18:30", color: "orange" },
	{ date: "2026-04-22", title: "Training — new operators", ticket: "SUPP-MOCK-0002", start: "13:30", end: "16:00", color: "blue" },
	{ date: "2026-04-25", title: "SLA review (internal)", ticket: "", color: "rose" },
	{ date: "2026-04-28", title: "Invoice & close batch", ticket: "SUPP-MOCK-0003", start: "11:00", end: "12:00", color: "purple" },
];
