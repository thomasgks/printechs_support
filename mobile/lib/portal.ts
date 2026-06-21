import { callMethod } from '@/lib/frappe-api';

export type PortalBootstrap =
	| { logged_in: false }
	| {
			logged_in: true;
			user: string;
			full_name: string;
			customers: string[];
			internal: boolean;
	  };

export async function getPortalBootstrap(): Promise<PortalBootstrap> {
	return callMethod<PortalBootstrap>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_bootstrap',
	);
}

export type DashboardStats = {
	pending_tickets: number;
	overdue_tickets: number;
	tickets_waiting_customer: number;
	tickets_waiting_internal: number;
	pending_tasks: number;
	overdue_tasks: number;
	completed_today: number;
	waiting_customer: number;
	waiting_internal: number;
	sla_breached: number;
	delayed_flagged: number;
	tickets_by_status: Record<string, number>;
	tasks_by_status: Record<string, number>;
	assignee_load: { name: string; count: number }[];
	monthly_completion: { month: string; label: string; count: number }[];
};

export async function getPortalDashboardStats(): Promise<DashboardStats> {
	return callMethod<DashboardStats>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_dashboard_stats',
	);
}

export async function getPortalTickets(
	limit = 50,
	opts?: { search?: string; activeOnly?: boolean },
): Promise<Record<string, unknown>[]> {
	return callMethod<Record<string, unknown>[]>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_tickets',
		{
			limit,
			search: opts?.search?.trim() ?? '',
			active_only: opts?.activeOnly === true ? 1 : 0,
		},
	);
}

export async function getPortalTasks(limit = 50): Promise<Record<string, unknown>[]> {
	return callMethod<Record<string, unknown>[]>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_tasks',
		{ limit },
	);
}

export async function getPortalTicket(name: string): Promise<Record<string, unknown>> {
	return callMethod<Record<string, unknown>>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_ticket',
		{ name },
	);
}

export async function getPortalTask(name: string): Promise<Record<string, unknown>> {
	return callMethod<Record<string, unknown>>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_task',
		{ name },
	);
}

export type TicketComment = {
	name?: string;
	comment_type?: string;
	comment_by?: string;
	author_name?: string;
	comment_on?: string | null;
	creation?: string;
	content?: string;
	is_customer_visible?: number;
	internal_only?: boolean;
};

export async function getPortalTicketComments(ticketName: string): Promise<TicketComment[]> {
	return callMethod<TicketComment[]>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_comments',
		{ ticket_name: ticketName },
	);
}

export async function getPortalTaskComments(taskName: string): Promise<TicketComment[]> {
	return callMethod<TicketComment[]>(
		'printechs_support.printechs_support_system.api.portal_api.get_portal_task_comments',
		{ task_name: taskName },
	);
}

export async function addPortalTicketComment(
	ticketName: string,
	content: string,
	isInternalNote = false,
): Promise<{ ok: boolean }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.add_portal_ticket_comment', {
		ticket_name: ticketName,
		content,
		is_internal_note: isInternalNote ? 1 : 0,
	});
}

export async function addPortalTaskComment(
	taskName: string,
	content: string,
	isInternalNote = false,
	opts?: { inReplyTo?: string; attachment?: string },
): Promise<{ ok: boolean }> {
	const payload: Record<string, unknown> = {
		task_name: taskName,
		content,
		is_internal_note: isInternalNote ? 1 : 0,
	};
	const r = opts?.inReplyTo?.trim();
	if (r) {
		payload.in_reply_to = r;
	}
	const a = opts?.attachment?.trim();
	if (a) {
		payload.attachment = a;
	}
	return callMethod('printechs_support.printechs_support_system.api.portal_api.add_portal_task_comment', payload);
}

export type TicketCustomerRow = { name: string; customer_name: string };

export async function getPortalTicketCustomers(): Promise<{ customers: TicketCustomerRow[] }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_customers');
}

export type TicketTypeRow = { name: string; label: string; division: string };

export async function getPortalTicketTypes(customer?: string): Promise<{
	types: TicketTypeRow[];
	restricted?: boolean;
}> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_types', {
		customer: customer?.trim() ?? '',
	});
}

export async function createPortalTicket(args: {
	subject: string;
	description?: string;
	priority?: string;
	customer?: string;
	ticket_type: string;
}): Promise<{ name: string; subject: string; status: string }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.create_portal_ticket', args);
}

export async function updatePortalTicketDueDate(
	ticketName: string,
	dueDate: string | null,
): Promise<{ ok: boolean; due_date: string | null; due_date_calendar?: string | null }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_ticket_due_date', {
		ticket_name: ticketName,
		due_date: dueDate ?? '',
	});
}

export async function updatePortalTaskDueDate(
	taskName: string,
	dueDate: string | null,
): Promise<{ ok: boolean; due_date: string | null; due_date_calendar?: string | null }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_task_due_date', {
		task_name: taskName,
		due_date: dueDate ?? '',
	});
}

export async function updatePortalTicketStatus(
	ticketName: string,
	status: string,
): Promise<{ ok: boolean; status: string }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_ticket_status', {
		ticket_name: ticketName,
		status,
	});
}

export async function updatePortalTaskStatus(
	taskName: string,
	status: string,
): Promise<{ ok: boolean; status: string }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_task_status', {
		task_name: taskName,
		status,
	});
}

/** Internal users only */
export async function updatePortalTicketAssignment(
	ticketName: string,
	args: { team?: string; assignees?: string[] },
): Promise<{ ok: boolean; team: string; assigned_to: string; assigned_users: string[]; status: string }> {
	const payload: Record<string, unknown> = { ticket_name: ticketName };
	if (args.team !== undefined) {
		payload.team = args.team;
	}
	if (args.assignees !== undefined) {
		payload.assignees = JSON.stringify(args.assignees);
	}
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_ticket_assignment', payload);
}

/** Internal users only */
export async function updatePortalTaskAssignment(
	taskName: string,
	assignees: string[],
): Promise<{ ok: boolean; assigned_to_user: string; assigned_users: string[] }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_task_assignment', {
		task_name: taskName,
		assignees: JSON.stringify(assignees),
	});
}

export async function getPortalTeams(): Promise<{ teams: { name: string; label: string }[] }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_teams');
}

export async function getPortalAssignmentUsers(limit = 200): Promise<{
	users: { name: string; full_name: string }[];
}> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_assignment_users', {
		limit,
	});
}

export async function getPortalTicketStatusOptions(ticketName?: string): Promise<{ options: string[] }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_ticket_status_options', {
		ticket_name: ticketName ?? '',
	});
}

export async function getPortalTaskStatusOptions(): Promise<{ options: string[] }> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_task_status_options');
}

export async function createPortalSupportTask(args: {
	support_ticket?: string;
	subject: string;
	task_type?: string;
	due_date?: string | null;
	division?: string;
	description?: string;
	responsible_side?: 'Printechs' | 'Customer';
}): Promise<{ name: string; subject: string; status: string; support_ticket: string | null; division?: string | null; responsible_side?: string; customer?: string | null }> {
	const payload: Record<string, unknown> = {
		subject: args.subject,
		task_type: args.task_type ?? '',
		due_date: args.due_date ?? '',
		description: args.description?.trim() ?? '',
		responsible_side: args.responsible_side ?? 'Printechs',
	};
	const st = (args.support_ticket ?? '').trim();
	if (st) {
		payload.support_ticket = st;
	} else {
		payload.division = (args.division ?? '').trim();
	}
	return callMethod('printechs_support.printechs_support_system.api.portal_api.create_portal_support_task', payload);
}

/** Internal: subject + description. Customers (ticket-linked task): description only. */
export async function updatePortalTask(
	taskName: string,
	args: { subject?: string; description?: string },
): Promise<{ ok: boolean; name: string; subject: string; status: string }> {
	const payload: Record<string, unknown> = { task_name: taskName.trim() };
	if (args.subject !== undefined) {
		payload.subject = args.subject;
	}
	if (args.description !== undefined) {
		payload.description = args.description;
	}
	return callMethod('printechs_support.printechs_support_system.api.portal_api.update_portal_task', payload);
}

export async function getPortalTasksForTicket(
	ticketName: string,
	limit = 100,
): Promise<Record<string, unknown>[]> {
	return callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_tasks_for_ticket', {
		ticket_name: ticketName.trim(),
		limit,
	});
}
