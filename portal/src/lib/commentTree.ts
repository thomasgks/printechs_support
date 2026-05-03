import type { PortalComment } from "../types/portal";

export type CommentThreadNode = {
	comment: PortalComment;
	/** Direct parent message when this row is a threaded reply. */
	parent: PortalComment | null;
	children: CommentThreadNode[];
};

/** Parse Frappe-style "YYYY-MM-DD HH:mm:ss" or ISO for stable sort. */
export function parseCommentTime(commentOn: string | null | undefined): number {
	if (!commentOn) {
		return 0;
	}
	const s = String(commentOn).trim();
	const isoLike = s.includes("T") ? s : s.replace(" ", "T");
	const t = Date.parse(isoLike);
	return Number.isNaN(t) ? 0 : t;
}

function compareCommentsAsc(a: PortalComment, b: PortalComment): number {
	return parseCommentTime(a.comment_on) - parseCommentTime(b.comment_on);
}

function compareCommentsDesc(a: PortalComment, b: PortalComment): number {
	return parseCommentTime(b.comment_on) - parseCommentTime(a.comment_on);
}

/** Group flat API rows into a tree by optional ``in_reply_to`` (sibling row name). */
export function buildCommentTree(comments: PortalComment[]): CommentThreadNode[] {
	if (!comments.length) {
		return [];
	}
	const byName = new Map<string, PortalComment>();
	for (const c of comments) {
		if (c.name) {
			byName.set(c.name, c);
		}
	}
	const childrenByParent = new Map<string, PortalComment[]>();
	for (const c of comments) {
		const pid = (c.in_reply_to || "").trim();
		if (!pid || !byName.has(pid)) {
			continue;
		}
		if (!childrenByParent.has(pid)) {
			childrenByParent.set(pid, []);
		}
		childrenByParent.get(pid)!.push(c);
	}
	for (const list of childrenByParent.values()) {
		list.sort(compareCommentsAsc);
	}
	const roots = comments.filter((c) => {
		const pid = (c.in_reply_to || "").trim();
		return !pid || !byName.has(pid);
	});
	/* Newest root threads first (common for support); replies under a thread stay oldest→newest. */
	roots.sort(compareCommentsDesc);

	function wrap(c: PortalComment, parent: PortalComment | null): CommentThreadNode {
		const kids = (c.name && childrenByParent.get(c.name)) || [];
		return {
			comment: c,
			parent,
			children: kids.map((k) => wrap(k, c)),
		};
	}
	return roots.map((r) => wrap(r, null));
}

export function stripHtmlToPlain(html: string, maxLen = 160): string {
	const t = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
	if (t.length <= maxLen) {
		return t;
	}
	return `${t.slice(0, maxLen).trim()}…`;
}

/** System Update rows (status, due date, etc.) vs threaded messages. */
export function isSystemUpdateComment(c: PortalComment): boolean {
	return (c.comment_type || "").trim() === "System Update";
}

/**
 * Split API rows for UI: messages for the main thread, system lines for the activity log.
 * Drops reply links that point to a system row when building the message tree.
 */
export function splitConversationAndActivityLog(comments: PortalComment[]): {
	messages: PortalComment[];
	activityLog: PortalComment[];
} {
	const activityLog = comments.filter(isSystemUpdateComment);
	activityLog.sort((a, b) => parseCommentTime(a.comment_on) - parseCommentTime(b.comment_on));

	const rawMessages = comments.filter((c) => !isSystemUpdateComment(c));
	const messageNames = new Set(rawMessages.map((m) => m.name).filter(Boolean));
	const messages = rawMessages.map((m) => {
		const pid = (m.in_reply_to || "").trim();
		if (pid && !messageNames.has(pid)) {
			return { ...m, in_reply_to: undefined };
		}
		return m;
	});

	return { messages, activityLog };
}
