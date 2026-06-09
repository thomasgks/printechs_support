export type PortalComment = {
	name?: string;
	comment_type: string;
	display_comment_type?: string;
	comment_by: string;
	author_name: string;
	author_is_internal?: boolean;
	comment_on: string | null;
	is_customer_visible: number;
	content: string;
	/** Sibling Support Ticket Comment row name (threaded reply). */
	in_reply_to?: string | null;
	attachment?: string | null;
	attachment_url?: string | null;
	internal_only?: boolean;
	/** Row from ticket thread vs merged-in Support Task comment (ticket view only). */
	thread_scope?: "ticket" | "task";
	task_name?: string;
	task_subject?: string;
};

export type PortalFileRow = {
	name: string;
	file_name: string;
	file_url: string;
	file_size?: number;
	creation?: string | null;
	owner?: string;
};
