import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent, ReactNode, RefObject } from "react";
import { Link } from "react-router-dom";
import {
	addPortalTaskComment,
	addPortalTicketComment,
	getPortalBootstrap,
	getPortalTaskComments,
	getPortalTicketComments,
	getPortalTicketDeskHistory,
	portalTaskPath,
	uploadPortalTaskFile,
	uploadPortalTicketFile,
	type PortalBootstrapResult,
	type PortalComment,
	type PortalDeskHistoryEntry,
} from "../api";
import {
	buildCommentTree,
	splitConversationAndActivityLog,
	stripHtmlToPlain,
	type CommentThreadNode,
} from "../lib/commentTree";
import { rewriteDeskHtmlLinks } from "../lib/deskLinks";
import { formatCommentTime } from "../lib/formatTime";

/** Persisted show/hide for System Update cards (activity log section). */
const STORAGE_KEY_ACTIVITY_LOG = "printechs_portal_show_ticket_activity_log";

/** Distance from bottom (px) to treat the thread as “following” latest messages (WhatsApp-style). */
const THREAD_STICK_TO_BOTTOM_PX = 100;

/** Curated statuses for internal users posting a reply (avoid closing the ticket from the composer). */
const PORTAL_TICKET_SEND_STATUS_OPTIONS: { value: string; label: string }[] = [
	{ value: "", label: "Do not change status" },
	{ value: "Open", label: "Open" },
	{ value: "Assigned", label: "Assigned" },
	{ value: "In Progress", label: "In Progress" },
	{ value: "Hold", label: "Hold" },
	{ value: "Waiting for Customer", label: "Waiting for Customer" },
	{ value: "Waiting for Technician", label: "Waiting for Technician" },
	{ value: "Resolved", label: "Resolved" },
	{ value: "Closed", label: "Closed" },
	{ value: "Cancelled", label: "Cancelled" },
];

const PORTAL_TASK_SEND_STATUS_OPTIONS: { value: string; label: string }[] = [
	{ value: "", label: "Do not change status" },
	{ value: "Open", label: "Open" },
	{ value: "In Progress", label: "In Progress" },
	{ value: "Waiting for Customer", label: "Waiting for Customer" },
	{ value: "Waiting for Printechs", label: "Waiting for Printechs" },
	{ value: "Delayed", label: "Delayed" },
];

type Props = {
	/** Support Ticket name — use for ticket-wide thread (exactly one of ticketName / taskName). */
	ticketName?: string;
	/** Support Task name — use for task-specific discussion (exactly one of ticketName / taskName). */
	taskName?: string;
	/** Current ticket status (portal) — used for customer “Waiting for Customer” reply behavior. */
	ticketStatus?: string;
	subtitle?: string;
	/** When true, no new messages or attachments (resolved/closed / terminal). */
	communicationLocked?: boolean;
	/** Called after a message posts successfully — use to refetch ticket header (status, due, etc.). */
	onAfterMessageSent?: () => void | Promise<void>;
};

function IconChatBubble({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
			/>
		</svg>
	);
}

function IconSend({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
			<path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" />
		</svg>
	);
}

function IconInbox({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.792m-18 0v-3a2.25 2.25 0 012.25-2.25h15A2.25 2.25 0 0121.75 10v3m-18 0A2.25 2.25 0 005.25 15h13.5a2.25 2.25 0 002.25-2.25m-18 0v-1.5A2.25 2.25 0 015.25 9h13.5a2.25 2.25 0 012.25 2.25v1.5"
			/>
		</svg>
	);
}

function IconLock({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M16.5 10.5V6.75a4.5 4.5 0 00-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
			/>
		</svg>
	);
}

function IconSparkles({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
			/>
		</svg>
	);
}

function IconClock({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
			<path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
	);
}

function IconPaperclip({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.381l-7.69 7.69"
			/>
		</svg>
	);
}

function IconRefresh({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
			/>
		</svg>
	);
}

function IconReplyArrow({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
			<path strokeLinecap="round" strokeLinejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 016 6v3" />
		</svg>
	);
}

function IconArrowDownCircle({ className }: { className?: string }) {
	return (
		<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
			<path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75l3 3m0 0l3-3m-3 3v-7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
	);
}

/** ERPNext stores technical types; friendlier labels so "Customer Reply" is not mistaken for a disabled action. */
function commentTypeLabel(raw: string | undefined): string {
	switch (raw) {
		case "Customer Reply":
			return "Message";
		case "Internal Note":
			return "Internal note";
		case "System Update":
			return "System update";
		case "Email":
			return "Email";
		default:
			return raw || "Message";
	}
}

function initialsFrom(authorName: string, commentBy: string): string {
	const s = (authorName || commentBy || "").trim();
	if (!s) {
		return "?";
	}
	const parts = s.split(/\s+/).filter(Boolean);
	if (parts.length >= 2) {
		const a = parts[0]!.charAt(0);
		const b = parts[parts.length - 1]!.charAt(0);
		return (a + b).toUpperCase().slice(0, 2);
	}
	return s.slice(0, 2).toUpperCase();
}

/** Customer vs technician lane depends on who is viewing (portal customer vs Desk internal user). */
function getConversationRole(
	viewerIsInternalUser: boolean,
	isMe: boolean,
	showInternalBadge: boolean,
): "customer" | "technician" {
	if (!viewerIsInternalUser) {
		return isMe ? "customer" : "technician";
	}
	if (showInternalBadge) {
		return "technician";
	}
	return isMe ? "technician" : "customer";
}

function CommentThreadBlock({
	nodes,
	currentUser,
	viewerIsInternalUser,
	onReplyTo,
	replyTargetId,
	inlineComposer,
	repliesDisabled,
}: {
	nodes: CommentThreadNode[];
	currentUser: string;
	viewerIsInternalUser: boolean;
	onReplyTo: (c: PortalComment) => void;
	replyTargetId?: string | null;
	inlineComposer?: (c: PortalComment) => ReactNode;
	repliesDisabled?: boolean;
}) {
	return (
		<div className="space-y-3">
			{nodes.map((node) => (
				<div key={node.comment.name ?? `${node.comment.comment_on}-${node.comment.comment_by}`}>
					<MessageBubble
						c={node.comment}
						currentUser={currentUser}
						viewerIsInternalUser={viewerIsInternalUser}
						parentComment={node.parent}
						onReply={() => onReplyTo(node.comment)}
						repliesDisabled={repliesDisabled}
					/>
					{replyTargetId && inlineComposer && node.comment.name && replyTargetId === node.comment.name ? (
						<div className="mt-2">{inlineComposer(node.comment)}</div>
					) : null}
					{node.children.length > 0 ? (
						<div className="mt-3 space-y-3 rounded-r-2xl border border-indigo-100/90 bg-indigo-50/50 py-3 pl-3 sm:ml-2 sm:border-l-2 sm:border-indigo-200 sm:pl-4">
							<CommentThreadBlock
								nodes={node.children}
								currentUser={currentUser}
								viewerIsInternalUser={viewerIsInternalUser}
								onReplyTo={onReplyTo}
								replyTargetId={replyTargetId}
								inlineComposer={inlineComposer}
								repliesDisabled={repliesDisabled}
							/>
						</div>
					) : null}
				</div>
			))}
		</div>
	);
}

function isLikelyImageUrl(url: string): boolean {
	const base = url.split("?")[0] ?? "";
	return /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(base);
}

function AttachmentComposerRow({
	fileInputRef,
	uploading,
	pending,
	attachErr,
	disabled,
	onPick,
	onFileChange,
	onRemove,
}: {
	fileInputRef: RefObject<HTMLInputElement | null>;
	uploading: boolean;
	pending: { file_name: string; file_url: string } | null;
	attachErr: string | null;
	disabled: boolean;
	onPick: () => void;
	onFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
	onRemove: () => void;
}) {
	return (
		<div className="mb-3">
			<input
				ref={fileInputRef}
				type="file"
				accept="image/*"
				className="sr-only"
				aria-label="Attach image"
				disabled={disabled || uploading}
				onChange={onFileChange}
			/>
			<div className="flex flex-wrap items-center gap-2">
				<button
					type="button"
					className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-violet-300 hover:bg-violet-50/80 hover:text-violet-900 disabled:opacity-60"
					disabled={disabled || uploading}
					onClick={onPick}
				>
					{uploading ? (
						<span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
					) : (
						<IconPaperclip className="h-4 w-4 text-violet-600" />
					)}
					{uploading ? "Uploading…" : "Add photo"}
				</button>
				<span className="text-xs text-slate-500">Images only · shown in the thread after you post</span>
			</div>
			{pending ? (
				<div className="mt-2 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">
					<img
						src={pending.file_url}
						alt=""
						className="h-20 w-20 rounded-lg object-cover ring-1 ring-slate-200"
					/>
					<div className="min-w-0 flex-1">
						<p className="truncate text-sm font-medium text-slate-800">{pending.file_name}</p>
						<button
							type="button"
							className="mt-1 text-xs font-semibold text-red-600 underline hover:text-red-800"
							onClick={onRemove}
						>
							Remove
						</button>
					</div>
				</div>
			) : null}
			{attachErr ? <p className="mt-2 text-xs text-red-600">{attachErr}</p> : null}
		</div>
	);
}

function ReplyContextStripe({ parent }: { parent: PortalComment }) {
	const who = String(parent.author_name || parent.comment_by || "Message");
	return (
		<div className="mb-2 flex flex-wrap items-start gap-2 rounded-xl border border-indigo-200/80 bg-white/90 px-3 py-2 text-left shadow-sm ring-1 ring-indigo-100/80">
			<IconReplyArrow className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
			<div className="min-w-0 flex-1">
				<p className="text-[0.65rem] font-bold uppercase tracking-wide text-indigo-800">Reply in thread</p>
				<p className="text-xs font-semibold text-slate-800">To {who}</p>
				<p className="mt-0.5 line-clamp-2 text-xs text-slate-600">{stripHtmlToPlain(parent.content, 140)}</p>
			</div>
		</div>
	);
}

function MessageBubble({
	c,
	currentUser,
	viewerIsInternalUser,
	parentComment,
	onReply,
	repliesDisabled,
}: {
	c: PortalComment;
	currentUser: string;
	viewerIsInternalUser: boolean;
	parentComment?: PortalComment | null;
	onReply: () => void;
	repliesDisabled?: boolean;
}) {
	const isMe = Boolean(currentUser && c.comment_by === currentUser);
	const showInternalBadge = Boolean(c.internal_only || c.comment_type === "Internal Note");
	const isSystem = c.comment_type === "System Update";
	const author = String(c.author_name || c.comment_by || "User");
	const initials = initialsFrom(String(c.author_name ?? ""), String(c.comment_by ?? ""));
	const hasParent = Boolean(parentComment);
	const role = getConversationRole(viewerIsInternalUser, isMe, showInternalBadge);
	const isCustomerLane = role === "customer";
	const isMergedTaskMessage = c.thread_scope === "task";
	/** Ticket composer cannot thread-reply to Support Task Comment rows (invalid ``in_reply_to`` server-side). */
	const blockReply = Boolean(repliesDisabled || isMergedTaskMessage);

	if (isSystem) {
		return (
			<div className="rounded-2xl border border-violet-200/90 bg-gradient-to-r from-violet-50 to-indigo-50 px-4 py-3 shadow-sm">
				{isMergedTaskMessage && c.task_name ? (
					<div className="mb-2 flex flex-wrap items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-wide text-indigo-800">
						<span className="rounded-full bg-indigo-100 px-2 py-0.5 ring-1 ring-indigo-200">Task thread</span>
						<Link
							to={portalTaskPath(String(c.task_name))}
							className="normal-case font-medium text-indigo-900 underline-offset-2 hover:underline"
						>
							{String(c.task_subject || c.task_name)}
						</Link>
					</div>
				) : null}
				{hasParent && parentComment ? <ReplyContextStripe parent={parentComment} /> : null}
				<div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-[0.7rem] font-bold uppercase tracking-wide text-violet-800">
					<div className="flex min-w-0 flex-wrap items-center justify-center gap-2 sm:justify-start">
						<IconSparkles className="h-3.5 w-3.5 shrink-0" />
						<span>{commentTypeLabel(c.comment_type)}</span>
						<span className="font-normal normal-case text-violet-600">
							<IconClock className="mr-0.5 inline h-3 w-3 opacity-80" />
							{formatCommentTime(c.comment_on)}
						</span>
					</div>
					{blockReply ? null : (
						<button
							type="button"
							className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-violet-400/90 bg-white px-3 py-1.5 text-xs font-bold text-violet-900 shadow-sm transition hover:bg-violet-100"
							onClick={onReply}
						>
							<IconReplyArrow className="h-3.5 w-3.5" />
							Reply
						</button>
					)}
				</div>
				<div
					className="portal-thread-html portal-thread-html--system max-w-none text-left"
					dangerouslySetInnerHTML={{ __html: rewriteDeskHtmlLinks(c.content) }}
				/>
			</div>
		);
	}

	const roleTitle = isCustomerLane ? "Customer" : "Technician";
	const avatarClass = isCustomerLane
		? "bg-emerald-600 text-white ring-2 ring-emerald-200/90"
		: showInternalBadge
			? "bg-amber-600 text-white ring-2 ring-amber-200/80"
			: "bg-slate-800 text-white ring-2 ring-slate-300/70";
	const bubbleSurface = showInternalBadge
		? "border border-amber-300/90 bg-amber-50/95 shadow-sm ring-1 ring-amber-100"
		: isCustomerLane
			? "border border-slate-200/90 bg-[#F1F1F1] shadow-sm"
			: "border border-sky-200/70 bg-[#E7F0FF] shadow-sm";
	const replyBtnClass = showInternalBadge
		? "border-amber-300 bg-amber-50 text-amber-950 hover:bg-amber-100"
		: isCustomerLane
			? "border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
			: "border-sky-300 bg-white text-sky-950 hover:bg-sky-50";

	return (
		<div className={`flex w-full ${isCustomerLane ? "justify-start" : "justify-end"}`}>
			<article
				className={`flex max-w-[min(100%,34rem)] gap-3 ${isCustomerLane ? "flex-row" : "flex-row-reverse"}`}
				aria-label={`${roleTitle}: ${author}`}
			>
				<div
					className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-bold ${avatarClass}`}
					aria-hidden
				>
					{initials}
				</div>
				<div className={`min-w-0 flex-1 rounded-2xl px-4 py-3 ${bubbleSurface} ${hasParent ? "ring-1 ring-indigo-100/90" : ""}`}>
					{isMergedTaskMessage && c.task_name ? (
						<div className="mb-2 flex flex-wrap items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-wide text-indigo-800">
							<span className="rounded-full bg-indigo-100 px-2 py-0.5 ring-1 ring-indigo-200">Task thread</span>
							<Link
								to={portalTaskPath(String(c.task_name))}
								className="normal-case font-medium text-indigo-900 underline-offset-2 hover:underline"
							>
								{String(c.task_subject || c.task_name)}
							</Link>
						</div>
					) : null}
					{hasParent && parentComment ? <ReplyContextStripe parent={parentComment} /> : null}
					<div className="mb-2 flex flex-wrap items-start justify-between gap-2">
						<div className="min-w-0">
							<div className="flex flex-wrap items-center gap-2">
								<span className="text-[0.7rem] font-extrabold uppercase tracking-wide text-slate-700">{roleTitle}</span>
								{showInternalBadge ? (
									<span className="inline-flex items-center gap-1 rounded-full bg-amber-200/90 px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-wide text-amber-950">
										<IconLock className="h-3 w-3" />
										Internal
									</span>
								) : null}
							</div>
							<p className="mt-0.5 font-semibold text-slate-900">{author}</p>
						</div>
						{blockReply ? null : (
							<button
								type="button"
								className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold shadow-sm transition ${replyBtnClass}`}
								onClick={onReply}
							>
								<IconReplyArrow className="h-3.5 w-3.5" />
								Reply
							</button>
						)}
					</div>
					<div className="portal-thread-html max-w-none text-slate-900" dangerouslySetInnerHTML={{ __html: rewriteDeskHtmlLinks(c.content) }} />
					{c.attachment_url && isLikelyImageUrl(c.attachment_url) ? (
						<a
							href={c.attachment_url}
							target="_blank"
							rel="noreferrer"
							className="mt-3 block overflow-hidden rounded-xl border border-slate-200/80 bg-white/80 shadow-sm ring-1 ring-slate-100"
						>
							<img
								src={c.attachment_url}
								alt=""
								className="max-h-72 w-full object-contain"
								loading="lazy"
							/>
						</a>
					) : null}
					{c.attachment_url ? (
						<a
							href={c.attachment_url}
							className={`mt-2 inline-flex items-center gap-1.5 text-sm font-semibold underline underline-offset-2 ${
								isCustomerLane ? "text-emerald-800 hover:text-emerald-950" : "text-sky-800 hover:text-sky-950"
							}`}
							target="_blank"
							rel="noreferrer"
						>
							<IconPaperclip className="h-4 w-4 shrink-0" />
							{isLikelyImageUrl(c.attachment_url) ? "Open image" : "Attachment"}
						</a>
					) : null}
					<p className="mt-3 text-left text-[0.7rem] text-slate-500">
						<IconClock className="mr-0.5 inline h-3 w-3 opacity-70" aria-hidden />
						{formatCommentTime(c.comment_on)}
						<span className="text-slate-400"> · </span>
						<span title={c.comment_type}>{commentTypeLabel(c.comment_type)}</span>
					</p>
				</div>
			</article>
		</div>
	);
}

function ComposerForm({
	textareaRef,
	textareaId,
	draft,
	setDraft,
	sending,
	onSend,
	onComposerKeyDown,
	internalNote,
	setInternalNote,
	isInternalUser,
	sendErr,
	showKeyboardTip,
	variant = "default",
	attachmentSlot,
	canPost,
	conversationScope,
	statusAfterSend = "",
	setStatusAfterSend,
	statusAfterSendOptions = [],
	showCustomerAcknowledgementOnly = false,
	customerAcknowledgementOnly = false,
	setCustomerAcknowledgementOnly,
	showStaffReplyIntent = false,
	staffReplyIntent = "normal_reply",
	setStaffReplyIntent,
	statusAfterSendForOverlay = "",
}: {
	textareaRef: RefObject<HTMLTextAreaElement | null>;
	textareaId: string;
	draft: string;
	setDraft: (v: string) => void;
	sending: boolean;
	onSend: () => void | Promise<void>;
	onComposerKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
	internalNote: boolean;
	setInternalNote: (v: boolean) => void;
	isInternalUser: boolean;
	sendErr: string | null;
	showKeyboardTip: boolean;
	variant?: "default" | "inline";
	attachmentSlot?: ReactNode;
	/** True when there is text and/or a prepared attachment to send. */
	canPost: boolean;
	/** "ticket" (default) or "task" — adjusts customer-visible copy. */
	conversationScope?: "ticket" | "task";
	/** Internal: optional ticket/task status applied together with this message. */
	statusAfterSend?: string;
	setStatusAfterSend?: (v: string) => void;
	statusAfterSendOptions?: { value: string; label: string }[];
	/** Customer + “Waiting for Customer”: optional “acknowledgment only” without handing back to support. */
	showCustomerAcknowledgementOnly?: boolean;
	customerAcknowledgementOnly?: boolean;
	setCustomerAcknowledgementOnly?: (v: boolean) => void;
	/** Internal + ticket: choose how smart workflow follows this customer-visible reply. */
	showStaffReplyIntent?: boolean;
	staffReplyIntent?: "none" | "normal_reply" | "expect_customer_response";
	setStaffReplyIntent?: (v: "none" | "normal_reply" | "expect_customer_response") => void;
	/** When non-empty, “Also set status” overrides automatic intent (disabled block). */
	statusAfterSendForOverlay?: string;
}) {
	const inline = variant === "inline";
	const scope = conversationScope ?? "ticket";
	const scopeNoun = scope === "task" ? "task" : "ticket";
	const setStatus = setStatusAfterSend ?? ((_v: string) => {});
	const showStatusSelect = isInternalUser && statusAfterSendOptions.length > 0;
	const statusOverridesIntent = Boolean((statusAfterSendForOverlay || "").trim());
	const setStaff = setStaffReplyIntent ?? ((_v: "none" | "normal_reply" | "expect_customer_response") => {});
	return (
		<>
			{isInternalUser ? (
				<label
					className={`flex cursor-pointer items-center gap-2.5 rounded-xl border border-amber-200/80 bg-amber-50/90 px-3 py-2.5 text-sm font-medium text-amber-950 ring-1 ring-amber-100 ${inline ? "mb-2" : "mb-3"}`}
				>
					<input
						type="checkbox"
						className="h-4 w-4 shrink-0 rounded border-amber-300 text-amber-700 focus:ring-amber-500"
						checked={internalNote}
						onChange={(e) => setInternalNote(e.target.checked)}
					/>
					<IconLock className="h-4 w-4 shrink-0 text-amber-800/90" />
					<span>Internal note — team only (customer cannot see this)</span>
				</label>
			) : inline ? (
				<p className="mb-2 text-xs text-slate-600">Visible to everyone on this {scopeNoun} who has access.</p>
			) : (
				<p className="mb-3 rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5 text-sm text-slate-600 ring-1 ring-slate-100">
					<strong className="font-semibold text-slate-800">Reply</strong> below. Your message is visible to everyone on this {scopeNoun} who has
					access. Staff-only internal notes never appear in your view.
				</p>
			)}
			{showCustomerAcknowledgementOnly && setCustomerAcknowledgementOnly ? (
				<label
					className={`flex cursor-pointer items-start gap-2.5 rounded-xl border border-sky-200/90 bg-sky-50/90 px-3 py-2.5 text-sm font-medium text-sky-950 ring-1 ring-sky-100 ${inline ? "mb-2" : "mb-3"}`}
				>
					<input
						type="checkbox"
						className="mt-0.5 h-4 w-4 shrink-0 rounded border-sky-300 text-sky-700 focus:ring-sky-500"
						checked={customerAcknowledgementOnly}
						disabled={sending}
						onChange={(e) => setCustomerAcknowledgementOnly(e.target.checked)}
					/>
					<span>
						<strong className="font-semibold text-sky-950">Quick acknowledgment only</strong> — keeps “Waiting for Customer”. Leave unchecked to
						send your reply back to support (status becomes Waiting for Technician).
					</span>
				</label>
			) : null}
			{showStaffReplyIntent && scope === "ticket" && setStaffReplyIntent ? (
				<fieldset
					disabled={sending || statusOverridesIntent || internalNote}
					className={`space-y-2 rounded-xl border border-teal-200/90 bg-teal-50/80 px-3 py-2.5 text-sm text-teal-950 ring-1 ring-teal-100 ${inline ? "mb-2" : "mb-3"} disabled:opacity-60`}
				>
					<legend className="float-none px-1 text-[0.65rem] font-bold uppercase tracking-wide text-teal-900">
						Status automation (customer-visible reply)
					</legend>
					<p className="text-xs leading-snug text-teal-900/90">
						Pick how the ticket should route after this message. Ignored for internal notes. If you use{" "}
						<strong className="font-semibold text-teal-950">Also set status</strong> below, that wins instead.
					</p>
					<label className="flex cursor-pointer items-start gap-2">
						<input
							type="radio"
							className="mt-1 h-4 w-4 shrink-0 border-teal-300 text-teal-700 focus:ring-teal-500"
							name={`staff-intent-${textareaId}`}
							checked={staffReplyIntent === "normal_reply"}
							onChange={() => setStaff("normal_reply")}
						/>
						<span>
							<strong className="font-semibold">Normal reply</strong> — technician-side update (e.g. move toward{" "}
							<em>In Progress</em> when appropriate). Does not force <em>Waiting for Customer</em>.
						</span>
					</label>
					<label className="flex cursor-pointer items-start gap-2">
						<input
							type="radio"
							className="mt-1 h-4 w-4 shrink-0 border-teal-300 text-teal-700 focus:ring-teal-500"
							name={`staff-intent-${textareaId}`}
							checked={staffReplyIntent === "expect_customer_response"}
							onChange={() => setStaff("expect_customer_response")}
						/>
						<span>
							<strong className="font-semibold">Expecting response from customer</strong> — set status to{" "}
							<em>Waiting for Customer</em> (customer must act next).
						</span>
					</label>
					<label className="flex cursor-pointer items-start gap-2">
						<input
							type="radio"
							className="mt-1 h-4 w-4 shrink-0 border-teal-300 text-teal-700 focus:ring-teal-500"
							name={`staff-intent-${textareaId}`}
							checked={staffReplyIntent === "none"}
							onChange={() => setStaff("none")}
						/>
						<span>
							<strong className="font-semibold">No automatic routing</strong> — only change status if you use{" "}
							<em>Also set status</em> above, or leave the thread unchanged.
						</span>
					</label>
				</fieldset>
			) : null}
			{showStatusSelect ? (
				<label
					className={`flex flex-col gap-1.5 rounded-xl border border-violet-200/80 bg-violet-50/70 px-3 py-2.5 text-sm font-medium text-violet-950 ring-1 ring-violet-100 sm:flex-row sm:items-center sm:justify-between ${inline ? "mb-2" : "mb-3"}`}
				>
					<span className="shrink-0 text-violet-950">Also set status to…</span>
					<select
						className="min-w-0 flex-1 rounded-lg border border-violet-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-sm outline-none ring-violet-500/20 focus:border-violet-400 focus:ring-2"
						value={statusAfterSend}
						disabled={sending}
						onChange={(e) => setStatus(e.target.value)}
						aria-label={scope === "task" ? "Also set task status when posting" : "Also set ticket status when posting"}
					>
						{statusAfterSendOptions.map((o) => (
							<option key={o.value || "__none"} value={o.value}>
								{o.label}
							</option>
						))}
					</select>
				</label>
			) : null}
			{attachmentSlot}
			<label className="sr-only" htmlFor={textareaId}>
				Reply to thread
			</label>
			<textarea
				ref={textareaRef}
				id={textareaId}
				className={`w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm text-slate-900 shadow-inner outline-none ring-violet-500/15 placeholder:text-slate-400 focus:border-violet-400 focus:bg-white focus:ring-4 ${inline ? "min-h-[5rem]" : "min-h-[6rem]"}`}
				placeholder={
					isInternalUser
						? internalNote
							? "Internal note for your team only…"
							: "Write a reply visible to the customer. Line breaks are kept."
						: "Write your reply… Line breaks are kept. Press Ctrl+Enter or ⌘+Enter to send."
				}
				value={draft}
				disabled={sending}
				onChange={(e) => setDraft(e.target.value)}
				onKeyDown={onComposerKeyDown}
			/>
			<div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
				{showKeyboardTip ? (
					<p className="text-xs text-slate-500">
						<strong className="font-medium text-slate-600">Tip:</strong>{" "}
						<kbd className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700">⌘</kbd>{" "}
						+{" "}
						<kbd className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700">Enter</kbd>{" "}
						(Mac) or{" "}
						<kbd className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700">Ctrl</kbd>{" "}
						+{" "}
						<kbd className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700">Enter</kbd>{" "}
						(Windows/Linux) to send quickly.
					</p>
				) : (
					<span className="text-xs text-slate-500">
						<kbd className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700">⌘</kbd>
						+
						<kbd className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700">Enter</kbd>{" "}
						to send
					</span>
				)}
				<button
					type="button"
					className={`portal-btn-primary inline-flex shrink-0 items-center justify-center gap-2 rounded-2xl px-6 py-3 text-sm font-bold shadow-lg transition ${
						sending ? "pointer-events-none opacity-95" : ""
					}`}
					disabled={!canPost}
					aria-busy={sending}
					onClick={() => void onSend()}
				>
					{sending ? (
						<>
							<span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
							Sending…
						</>
					) : (
						<>
							<IconSend className="h-4 w-4 shrink-0 text-white" />
							Post reply
						</>
					)}
				</button>
			</div>
			{sendErr ? <p className="mt-2 text-sm text-red-600">{sendErr}</p> : null}
		</>
	);
}

export default function CommunicationPanel({
	ticketName,
	taskName,
	ticketStatus,
	subtitle,
	communicationLocked = false,
	onAfterMessageSent,
}: Props) {
	const hasTicket = Boolean(ticketName?.trim());
	const hasTask = Boolean(taskName?.trim());
	if (hasTicket === hasTask) {
		return (
			<section className="rounded-3xl border border-red-200 bg-red-50/90 p-5 text-sm text-red-950 shadow-sm">
				<p className="font-semibold">Communication panel misconfigured</p>
				<p className="mt-1">
					Pass exactly one of <span className="font-mono">ticketName</span> or <span className="font-mono">taskName</span>.
				</p>
			</section>
		);
	}
	const isTask = hasTask;

	const [comments, setComments] = useState<PortalComment[]>([]);
	const [draft, setDraft] = useState("");
	const [internalNote, setInternalNote] = useState(false);
	const [statusAfterSend, setStatusAfterSend] = useState("");
	const [lastStatusHint, setLastStatusHint] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [refreshing, setRefreshing] = useState(false);
	const [sending, setSending] = useState(false);
	const [bootstrap, setBootstrap] = useState<Extract<PortalBootstrapResult, { logged_in: true }> | null>(null);
	const [threadErr, setThreadErr] = useState<string | null>(null);
	const [sendErr, setSendErr] = useState<string | null>(null);
	const [replyTarget, setReplyTarget] = useState<PortalComment | null>(null);
	const threadScrollRef = useRef<HTMLDivElement>(null);
	const threadEndRef = useRef<HTMLDivElement>(null);
	/** While true, new messages trigger auto-scroll to the bottom; false after user scrolls up. */
	const stickToBottomRef = useRef(true);
	/** After posting a message we always reveal the newest entry. */
	const forceScrollNextRef = useRef<"none" | "auto" | "smooth">("none");
	const initialThreadScrollDoneRef = useRef(false);
	const [showJumpToLatest, setShowJumpToLatest] = useState(false);
	const composerSectionRef = useRef<HTMLDivElement>(null);
	const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
	const inlineComposerTextareaRef = useRef<HTMLTextAreaElement>(null);
	const inlineAnchorRef = useRef<HTMLDivElement>(null);
	const attachmentFileInputRef = useRef<HTMLInputElement>(null);
	const [pendingAttachment, setPendingAttachment] = useState<{
		name: string;
		file_name: string;
		file_url: string;
	} | null>(null);
	const [uploadingFile, setUploadingFile] = useState(false);
	const [attachErr, setAttachErr] = useState<string | null>(null);
	const [deskHistory, setDeskHistory] = useState<PortalDeskHistoryEntry[]>([]);
	/** Default off so long ticket history does not overwhelm the thread; opt-in via switch. */
	const [showActivityLog, setShowActivityLog] = useState(false);
	const [customerAcknowledgementOnly, setCustomerAcknowledgementOnly] = useState(false);
	const [staffReplyIntent, setStaffReplyIntent] = useState<"none" | "normal_reply" | "expect_customer_response">(
		"normal_reply",
	);

	useEffect(() => {
		initialThreadScrollDoneRef.current = false;
		stickToBottomRef.current = true;
		forceScrollNextRef.current = "none";
		setShowJumpToLatest(false);
		setStatusAfterSend("");
		setLastStatusHint(null);
		setCustomerAcknowledgementOnly(false);
		setStaffReplyIntent("normal_reply");
	}, [ticketName, taskName]);

	useEffect(() => {
		try {
			const v = localStorage.getItem(STORAGE_KEY_ACTIVITY_LOG);
			if (v === "1" || v === "true") {
				setShowActivityLog(true);
			} else {
				setShowActivityLog(false);
			}
		} catch {
			/* ignore */
		}
	}, []);

	const setShowActivityLogPersist = useCallback((next: boolean) => {
		setShowActivityLog(next);
		try {
			localStorage.setItem(STORAGE_KEY_ACTIVITY_LOG, next ? "1" : "0");
		} catch {
			/* ignore */
		}
	}, []);

	const canPost = useMemo(
		() => !communicationLocked && Boolean(draft.trim() || pendingAttachment),
		[communicationLocked, draft, pendingAttachment],
	);

	const onAttachmentFileChange = useCallback(
		async (e: ChangeEvent<HTMLInputElement>) => {
			if (communicationLocked) {
				return;
			}
			const f = e.target.files?.[0];
			e.target.value = "";
			if (!f) {
				return;
			}
			setAttachErr(null);
			if (!f.type.startsWith("image/")) {
				setAttachErr("Please choose an image file.");
				return;
			}
			setUploadingFile(true);
			try {
				const r = isTask
					? await uploadPortalTaskFile(String(taskName).trim(), f)
					: await uploadPortalTicketFile(String(ticketName).trim(), f);
				setPendingAttachment({ name: r.name, file_name: r.file_name, file_url: r.file_url });
			} catch (err) {
				setAttachErr(err instanceof Error ? err.message : "Upload failed");
			} finally {
				setUploadingFile(false);
			}
		},
		[ticketName, taskName, isTask, communicationLocked],
	);

	const attachmentSlot = (
		<AttachmentComposerRow
			fileInputRef={attachmentFileInputRef}
			uploading={uploadingFile}
			pending={pendingAttachment}
			attachErr={attachErr}
			disabled={sending || communicationLocked}
			onPick={() => attachmentFileInputRef.current?.click()}
			onFileChange={onAttachmentFileChange}
			onRemove={() => {
				setPendingAttachment(null);
				setAttachErr(null);
			}}
		/>
	);

	const beginReply = useCallback(
		(target: PortalComment | null) => {
			if (communicationLocked) {
				return;
			}
			setReplyTarget(target);
			if (target === null) {
				composerSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
				window.setTimeout(() => {
					composerTextareaRef.current?.focus();
				}, 200);
			}
		},
		[communicationLocked],
	);

	const clearReplyTargetAndFocusBottom = useCallback(() => {
		setReplyTarget(null);
		window.setTimeout(() => {
			composerSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
			composerTextareaRef.current?.focus();
		}, 80);
	}, []);

	useEffect(() => {
		if (!replyTarget?.name) {
			return;
		}
		inlineAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
		const t = window.setTimeout(() => {
			inlineComposerTextareaRef.current?.focus();
		}, 300);
		return () => window.clearTimeout(t);
	}, [replyTarget]);

	const { messages: threadMessages, activityLog } = useMemo(
		() => splitConversationAndActivityLog(comments),
		[comments],
	);
	const messageTree = useMemo(() => buildCommentTree(threadMessages), [threadMessages]);
	const activityItemCount = activityLog.length + deskHistory.length;
	/** Task mode has no Desk history toggle; always show system updates when present. */
	const showActivityForUi = isTask || showActivityLog;

	const refreshThreadScrollIndicators = useCallback(() => {
		const el = threadScrollRef.current;
		if (!el) return;
		const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
		const nearBottom = gap <= THREAD_STICK_TO_BOTTOM_PX;
		stickToBottomRef.current = nearBottom;
		const scrollable = el.scrollHeight > el.clientHeight + 8;
		setShowJumpToLatest(Boolean(scrollable && !nearBottom));
	}, []);

	const jumpToLatest = useCallback(() => {
		threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
		stickToBottomRef.current = true;
		setShowJumpToLatest(false);
	}, []);

	useLayoutEffect(() => {
		if (loading || threadErr) return;

		const endEl = threadEndRef.current;

		const scheduleRefresh = () => requestAnimationFrame(() => refreshThreadScrollIndicators());

		if (replyTarget) {
			scheduleRefresh();
			return;
		}

		if (!endEl) {
			initialThreadScrollDoneRef.current = true;
			scheduleRefresh();
			return;
		}

		const mode = forceScrollNextRef.current;
		if (mode !== "none") {
			forceScrollNextRef.current = "none";
			endEl.scrollIntoView({ behavior: mode === "smooth" ? "smooth" : "auto", block: "end" });
			stickToBottomRef.current = true;
			scheduleRefresh();
			initialThreadScrollDoneRef.current = true;
			return;
		}

		if (!initialThreadScrollDoneRef.current) {
			initialThreadScrollDoneRef.current = true;
			endEl.scrollIntoView({ behavior: "auto", block: "end" });
			stickToBottomRef.current = true;
			scheduleRefresh();
			return;
		}

		if (stickToBottomRef.current) {
			endEl.scrollIntoView({ behavior: "smooth", block: "end" });
			scheduleRefresh();
		} else {
			scheduleRefresh();
		}
	}, [
		loading,
		threadErr,
		comments,
		replyTarget,
		showActivityForUi,
		deskHistory.length,
		activityLog.length,
		threadMessages.length,
		refreshThreadScrollIndicators,
	]);

	useEffect(() => {
		const el = threadScrollRef.current;
		if (!el || loading) return;
		const onScroll = () => refreshThreadScrollIndicators();
		el.addEventListener("scroll", onScroll, { passive: true });
		onScroll();
		return () => el.removeEventListener("scroll", onScroll);
	}, [
		loading,
		ticketName,
		taskName,
		comments.length,
		showActivityForUi,
		activityLog.length,
		deskHistory.length,
		threadMessages.length,
		refreshThreadScrollIndicators,
	]);

	const loadThread = useCallback(async () => {
		setThreadErr(null);
		setLoading(true);
		try {
			const [b, rows] = await Promise.all([
				getPortalBootstrap(),
				isTask ? getPortalTaskComments(String(taskName).trim()) : getPortalTicketComments(String(ticketName).trim()),
			]);
			if (b.logged_in) {
				setBootstrap(b);
			}
			setComments(rows);
			if (!isTask && b.logged_in && "internal" in b && b.internal) {
				try {
					const dh = await getPortalTicketDeskHistory(String(ticketName).trim());
					setDeskHistory(dh.entries);
				} catch {
					/* Older benches without get_portal_ticket_desk_history — thread still loads */
					setDeskHistory([]);
				}
			} else {
				setDeskHistory([]);
			}
		} catch (e) {
			setThreadErr(e instanceof Error ? e.message : "Could not load comments");
		} finally {
			setLoading(false);
		}
	}, [ticketName, taskName, isTask]);

	const softRefresh = useCallback(async () => {
		setThreadErr(null);
		setRefreshing(true);
		try {
			const [b, rows] = await Promise.all([
				getPortalBootstrap(),
				isTask ? getPortalTaskComments(String(taskName).trim()) : getPortalTicketComments(String(ticketName).trim()),
			]);
			if (b.logged_in) {
				setBootstrap(b);
			}
			setComments(rows);
			if (!isTask && b.logged_in && "internal" in b && b.internal) {
				try {
					const dh = await getPortalTicketDeskHistory(String(ticketName).trim());
					setDeskHistory(dh.entries);
				} catch {
					setDeskHistory([]);
				}
			} else {
				setDeskHistory([]);
			}
		} catch (e) {
			setThreadErr(e instanceof Error ? e.message : "Could not load comments");
		} finally {
			setRefreshing(false);
		}
	}, [ticketName, taskName, isTask]);

	useEffect(() => {
		loadThread();
	}, [loadThread]);

	useEffect(() => {
		if (communicationLocked) {
			setReplyTarget(null);
			setDraft("");
			setPendingAttachment(null);
			setStatusAfterSend("");
		}
	}, [communicationLocked]);

	const currentUser = bootstrap?.user ?? "";
	const isInternalUser = Boolean(bootstrap?.internal);
	const showCustomerAcknowledgementUi =
		hasTicket &&
		!isTask &&
		!isInternalUser &&
		(ticketStatus ?? "").trim() === "Waiting for Customer";
	const showStaffReplyIntentUi = hasTicket && !isTask && isInternalUser && !communicationLocked;
	const statusSendOptions = useMemo(() => {
		if (!isInternalUser || communicationLocked) {
			return [];
		}
		return isTask ? PORTAL_TASK_SEND_STATUS_OPTIONS : PORTAL_TICKET_SEND_STATUS_OPTIONS;
	}, [isInternalUser, communicationLocked, isTask]);
	const roleBlurbReady = !loading && bootstrap != null;

	const headerDescription =
		subtitle ??
		(!roleBlurbReady
			? "Loading conversation…"
			: isTask
				? isInternalUser
					? "Discuss this task with your team. Internal notes stay hidden from customers when the task is linked to a ticket. Latest messages stay at the bottom — scroll up for older."
					: "Discuss this task with your support team. Latest messages appear at the bottom — scroll up for older."
				: isInternalUser
					? "Post customer-visible replies or team-only internal notes. Latest messages stay at the bottom — scroll up for older."
					: "Read replies from your team and post your own below; latest messages appear at the bottom — scroll up for older. Plain text and line breaks are supported.");

	const onSend = async () => {
		if (sending) return;
		const text = draft.trim();
		if (!text && !pendingAttachment) return;
		setSendErr(null);
		setLastStatusHint(null);
		setSending(true);
		try {
			forceScrollNextRef.current = "smooth";
			const bodyHtml = text ? formatPlainAsHtml(text) : "";
			const extraStatus = (statusAfterSend || "").trim();
			const ticketOpts: {
				reply_mode?: "provide_information" | "acknowledgement_only";
				technician_reply_effect?: "normal_reply" | "expect_customer_response";
			} = {};
			if (showCustomerAcknowledgementUi) {
				ticketOpts.reply_mode = customerAcknowledgementOnly ? "acknowledgement_only" : "provide_information";
			}
			if (
				showStaffReplyIntentUi &&
				isInternalUser &&
				!internalNote &&
				!extraStatus &&
				staffReplyIntent !== "none"
			) {
				ticketOpts.technician_reply_effect =
					staffReplyIntent === "expect_customer_response" ? "expect_customer_response" : "normal_reply";
			}
			const hasTicketOpts = Object.keys(ticketOpts).length > 0;
			const res = isTask
				? await addPortalTaskComment(
						String(taskName).trim(),
						bodyHtml,
						isInternalUser && internalNote,
						replyTarget?.name ?? null,
						pendingAttachment?.name ?? null,
						isInternalUser && extraStatus ? extraStatus : null,
					)
				: await addPortalTicketComment(
						String(ticketName).trim(),
						bodyHtml,
						isInternalUser && internalNote,
						replyTarget?.name ?? null,
						pendingAttachment?.name ?? null,
						isInternalUser && extraStatus ? extraStatus : null,
						hasTicketOpts ? ticketOpts : undefined,
					);
			if (extraStatus && isInternalUser) {
				const st = isTask ? res.task_status : res.ticket_status;
				if (st) {
					setLastStatusHint(isTask ? `Task status set to ${st}.` : `Ticket status set to ${st}.`);
				}
			}
			setDraft("");
			setInternalNote(false);
			setCustomerAcknowledgementOnly(false);
			setStaffReplyIntent("normal_reply");
			setStatusAfterSend("");
			setReplyTarget(null);
			setPendingAttachment(null);
			setAttachErr(null);
			await loadThread();
			if (onAfterMessageSent) {
				try {
					await onAfterMessageSent();
				} catch {
					/* parent refresh is best-effort */
				}
			}
		} catch (e) {
			setSendErr(e instanceof Error ? e.message : "Send failed");
		} finally {
			setSending(false);
		}
	};

	const onComposerKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			if (canPost && !sending) {
				void onSend();
			}
		}
	};

	return (
		<section className="relative overflow-hidden rounded-3xl border border-slate-200/90 bg-slate-100/90 shadow-[0_20px_60px_-15px_rgba(79,70,229,0.12)]">
			<div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-violet-500 to-transparent opacity-90" />
			<div className="border-b border-slate-200/90 bg-white px-5 py-4 sm:px-6">
				<div className="flex flex-wrap items-start justify-between gap-3">
					<div className="flex min-w-0 items-start gap-3">
						<span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-700 ring-1 ring-violet-200/80">
							<IconChatBubble className="h-5 w-5" />
						</span>
						<div className="min-w-0">
							<h3 className="font-['Syne',system-ui,sans-serif] text-xl font-extrabold tracking-tight text-slate-900">
								{isTask ? "Task conversation" : "Conversation"}
							</h3>
							<p className="mt-1 text-sm leading-relaxed text-slate-600">{headerDescription}</p>
						</div>
					</div>
					<div className="flex flex-wrap items-center justify-end gap-2">
						{!isTask ? (
							<label
								className={`inline-flex select-none items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold shadow-sm ${
									loading || activityItemCount === 0
										? "cursor-not-allowed text-slate-400"
										: "cursor-pointer text-slate-700 transition hover:border-violet-300 hover:bg-violet-50/80"
								}`}
								title={
									activityItemCount === 0
										? "No thread system updates or Desk field history on this ticket yet."
										: "Show or hide Desk + thread activity below (keeps the conversation compact)."
								}
							>
								<input
									type="checkbox"
									className="h-4 w-4 shrink-0 rounded border-slate-300 text-violet-600 focus:ring-violet-500 disabled:opacity-50"
									checked={showActivityLog}
									onChange={(e) => setShowActivityLogPersist(e.target.checked)}
									disabled={loading || activityItemCount === 0}
								/>
								<span>Show activity log</span>
								{activityItemCount > 0 ? (
									<span className="rounded-full bg-violet-100 px-2 py-0.5 text-[0.65rem] font-bold text-violet-800">
										{activityItemCount}
									</span>
								) : (
									<span className="text-[0.65rem] font-medium text-slate-400">—</span>
								)}
							</label>
						) : null}
						<button
							type="button"
							className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-violet-300 hover:bg-violet-50/80 hover:text-violet-900"
							disabled={loading || refreshing}
							onClick={() => void softRefresh()}
							aria-busy={refreshing}
						>
							<IconRefresh className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
							Refresh
						</button>
					</div>
				</div>
			</div>

			<div
				ref={threadScrollRef}
				className="relative max-h-[min(80vh,720px)] overflow-y-auto border-b border-slate-200/80 bg-slate-100/80 px-3 py-4 sm:px-5"
			>
				{loading ? (
					<p className="py-8 text-center text-sm text-slate-600">Loading thread…</p>
				) : threadErr ? (
					<p className="py-8 text-center text-sm text-red-600">{threadErr}</p>
				) : comments.length === 0 && activityItemCount === 0 ? (
					<div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center shadow-sm">
						<div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-50 text-slate-400 ring-1 ring-slate-200">
							<IconInbox className="h-6 w-6" />
						</div>
						<p className="text-sm font-semibold text-slate-800">No messages yet</p>
						<p className="mt-1 text-xs text-slate-500">
							{isInternalUser
								? isTask
									? "Post a task update below, or wait for the customer to reply."
									: "Post an update below, or wait for the customer to reply."
								: isTask
									? "When your support team posts on this task, it will appear here. Use the box below to send your first message."
									: "When your support team replies, it will appear here. Use the box below to send your first message."}
						</p>
						{communicationLocked ? null : (
							<button
								type="button"
								className="mt-4 inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-800 shadow-sm transition hover:bg-indigo-100"
								onClick={() => beginReply(null)}
							>
								<IconReplyArrow className="h-4 w-4" />
								Write a reply
							</button>
						)}
					</div>
				) : (
					<div className="space-y-3">
						{threadMessages.length === 0 ? (
							<div className="rounded-2xl border border-dashed border-slate-200 bg-white/90 px-4 py-8 text-center shadow-sm">
								<p className="text-sm text-slate-700">No conversation messages in the thread yet.</p>
								{activityItemCount > 0 && !showActivityForUi ? (
									<p className="mx-auto mt-2 max-w-sm text-xs text-slate-500">
										Turn on <strong className="font-semibold text-slate-700">Show activity log</strong> above for Desk field
										history and system updates.
									</p>
								) : null}
							</div>
						) : (
							<CommentThreadBlock
								nodes={messageTree}
								currentUser={currentUser}
								viewerIsInternalUser={isInternalUser}
								onReplyTo={(c) => beginReply(c)}
								replyTargetId={replyTarget?.name}
								repliesDisabled={communicationLocked}
								inlineComposer={(c) => (
									<div
										ref={inlineAnchorRef}
										className="rounded-2xl border border-indigo-200/90 bg-gradient-to-b from-white to-indigo-50/50 p-4 shadow-md ring-1 ring-indigo-100"
									>
										<div className="mb-3 flex flex-wrap items-start justify-between gap-2">
											<div className="min-w-0">
												<p className="text-[0.65rem] font-bold uppercase tracking-wide text-indigo-800">Replying on this message</p>
												<p className="mt-0.5 font-semibold text-slate-900">{c.author_name || c.comment_by}</p>
												<p className="mt-1 line-clamp-2 text-xs text-slate-600">{stripHtmlToPlain(c.content)}</p>
											</div>
											<button
												type="button"
												className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
												onClick={() => setReplyTarget(null)}
											>
												Cancel
											</button>
										</div>
										<ComposerForm
											variant="inline"
											textareaRef={inlineComposerTextareaRef}
											textareaId={isTask ? "portal-task-reply-inline" : "portal-ticket-reply-inline"}
											draft={draft}
											setDraft={setDraft}
											sending={sending}
											onSend={onSend}
											onComposerKeyDown={onComposerKeyDown}
											internalNote={internalNote}
											setInternalNote={setInternalNote}
											isInternalUser={isInternalUser}
											sendErr={sendErr}
											showKeyboardTip={false}
											attachmentSlot={attachmentSlot}
											canPost={canPost}
											conversationScope={isTask ? "task" : "ticket"}
											statusAfterSend={statusAfterSend}
											setStatusAfterSend={setStatusAfterSend}
											statusAfterSendOptions={statusSendOptions}
											showCustomerAcknowledgementOnly={showCustomerAcknowledgementUi}
											customerAcknowledgementOnly={customerAcknowledgementOnly}
											setCustomerAcknowledgementOnly={setCustomerAcknowledgementOnly}
											showStaffReplyIntent={showStaffReplyIntentUi && !internalNote}
											staffReplyIntent={staffReplyIntent}
											setStaffReplyIntent={setStaffReplyIntent}
											statusAfterSendForOverlay={statusAfterSend}
										/>
									</div>
								)}
							/>
						)}

						{showActivityForUi && activityItemCount > 0 ? (
							<div className="mt-1">
								<div className="overflow-hidden rounded-2xl border border-violet-200/90 bg-gradient-to-br from-violet-50/90 via-white to-indigo-50/80 shadow-[0_8px_30px_-12px_rgba(79,70,229,0.25)] ring-1 ring-violet-100/80">
									<div className="flex flex-wrap items-center gap-2 border-b border-violet-200/60 bg-white/70 px-4 py-3">
										<IconSparkles className="h-4 w-4 shrink-0 text-violet-600" aria-hidden />
										<h4 className="font-['Syne',system-ui,sans-serif] text-sm font-extrabold uppercase tracking-wide text-slate-900">
											Activity &amp; updates
										</h4>
										<span className="rounded-full bg-violet-100 px-2 py-0.5 text-[0.65rem] font-bold text-violet-800">
											{activityItemCount}
										</span>
									</div>
									<div className="px-4 py-3">
										{deskHistory.length > 0 ? (
											<div className="mb-4 border-b border-violet-100/90 pb-4">
												<p className="mb-2 text-[0.65rem] font-bold uppercase tracking-wide text-slate-600">
													Desk form history
												</p>
												<p className="mb-2 text-[0.65rem] leading-snug text-slate-500">
													From Frappe <strong className="font-semibold text-slate-700">Versions</strong> (includes saves
													made directly on the ticket in Desk).
												</p>
												<ul className="space-y-3">
													{deskHistory.map((e) => (
														<li
															key={e.name}
															className="border-b border-violet-100/80 pb-3 last:border-b-0 last:pb-0"
														>
															<p className="text-[0.65rem] font-bold uppercase tracking-wide text-violet-800">
																<IconClock className="mr-0.5 inline h-3 w-3 opacity-80" aria-hidden />
																{e.at ? formatCommentTime(e.at) : "—"}{" "}
																<span className="font-semibold normal-case text-slate-800">
																	{e.user_full_name}
																</span>
																{e.impersonated_by ? (
																	<span className="ml-1 font-normal normal-case text-amber-700">
																		(via {e.impersonated_by})
																	</span>
																) : null}
															</p>
															<ul className="mt-1.5 list-none space-y-1 pl-0">
																{e.changes.map((ch, i) => (
																	<li key={`${e.name}-${i}-${ch.fieldname}`} className="text-xs text-slate-800">
																		<span className="font-semibold text-slate-900">{ch.label}</span>
																		<span className="text-slate-500">: </span>
																		<span className="break-words text-slate-600">{ch.old || "—"}</span>
																		<span className="text-slate-400"> → </span>
																		<span className="break-words text-slate-800">{ch.new || "—"}</span>
																	</li>
																))}
															</ul>
														</li>
													))}
												</ul>
											</div>
										) : null}
										{activityLog.length > 0 ? (
											<div>
												{deskHistory.length > 0 ? (
													<p className="mb-2 text-[0.65rem] font-bold uppercase tracking-wide text-slate-600">
														Thread — system updates
													</p>
												) : null}
												<ul className="space-y-3">
													{activityLog.map((c) => (
														<li
															key={c.name ?? `${c.comment_on}-${c.comment_by}-log`}
															className="border-b border-violet-100/90 pb-3 last:border-b-0 last:pb-0"
														>
															<p className="text-[0.65rem] font-bold uppercase tracking-wide text-violet-800">
																<IconClock className="mr-0.5 inline h-3 w-3 opacity-80" aria-hidden />
																{formatCommentTime(c.comment_on)}
															</p>
															<div
																className="portal-thread-html portal-thread-html--system mt-1.5 max-w-none text-left text-sm text-slate-800"
																dangerouslySetInnerHTML={{ __html: rewriteDeskHtmlLinks(c.content) }}
															/>
														</li>
													))}
												</ul>
											</div>
										) : null}
									</div>
								</div>
							</div>
						) : null}

						{!showActivityForUi && activityItemCount > 0 ? (
							<p className="rounded-xl border border-dashed border-slate-200/90 bg-white/70 px-3 py-2 text-center text-xs text-slate-600">
								{activityItemCount} item{activityItemCount === 1 ? "" : "s"} hidden (Desk history + thread updates) — turn on{" "}
								<strong className="font-semibold text-slate-800">Show activity log</strong> to open the card.
							</p>
						) : null}

						<div ref={threadEndRef} className="h-px w-full shrink-0" aria-hidden />
					</div>
				)}
				{showJumpToLatest ? (
					<button
						type="button"
						className="absolute bottom-4 right-4 z-10 inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-white px-4 py-2 text-sm font-bold text-slate-800 shadow-lg ring-1 ring-slate-200/80 transition hover:bg-slate-50"
						onClick={jumpToLatest}
					>
						<IconArrowDownCircle className="h-5 w-5 text-violet-600" />
						Latest messages
					</button>
				) : null}
			</div>

			<div ref={composerSectionRef} className="bg-white px-4 py-5 sm:px-6">
				{lastStatusHint ? (
					<p className="mb-3 rounded-xl border border-emerald-200 bg-emerald-50/90 px-3 py-2 text-sm font-medium text-emerald-900 ring-1 ring-emerald-100">
						{lastStatusHint}
					</p>
				) : null}
				{communicationLocked ? (
					<div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-center text-sm text-amber-950 shadow-sm">
						{isTask ? (
							<>
								<p className="font-semibold">Task discussion is closed.</p>
								<p className="mt-1 text-amber-900/90">
									New messages and attachments are disabled when the task is completed or cancelled, or when the linked ticket is
									resolved or closed. Reopen in Desk (or the ticket) to continue.
								</p>
							</>
						) : (
							<>
								<p className="font-semibold">This ticket is resolved or closed.</p>
								<p className="mt-1 text-amber-900/90">
									New messages and attachments are disabled. Reopen the ticket (e.g. set status to Reopened in Desk or from the portal if
									allowed) to continue the conversation.
								</p>
							</>
						)}
					</div>
				) : replyTarget ? (
					<p className="text-center text-sm text-slate-600">
						Replying in the thread above.{" "}
						<button
							type="button"
							className="font-semibold text-indigo-700 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-900"
							onClick={() => clearReplyTargetAndFocusBottom()}
						>
							Cancel and use composer here
						</button>
					</p>
				) : (
					<ComposerForm
						variant="default"
						textareaRef={composerTextareaRef}
						textareaId={isTask ? "portal-task-reply" : "portal-ticket-reply"}
						draft={draft}
						setDraft={setDraft}
						sending={sending}
						onSend={onSend}
						onComposerKeyDown={onComposerKeyDown}
						internalNote={internalNote}
						setInternalNote={setInternalNote}
						isInternalUser={isInternalUser}
						sendErr={sendErr}
						showKeyboardTip
						attachmentSlot={attachmentSlot}
						canPost={canPost}
						conversationScope={isTask ? "task" : "ticket"}
						statusAfterSend={statusAfterSend}
						setStatusAfterSend={setStatusAfterSend}
						statusAfterSendOptions={statusSendOptions}
						showCustomerAcknowledgementOnly={showCustomerAcknowledgementUi}
						customerAcknowledgementOnly={customerAcknowledgementOnly}
						setCustomerAcknowledgementOnly={setCustomerAcknowledgementOnly}
						showStaffReplyIntent={showStaffReplyIntentUi && !internalNote}
						staffReplyIntent={staffReplyIntent}
						setStaffReplyIntent={setStaffReplyIntent}
						statusAfterSendForOverlay={statusAfterSend}
					/>
				)}
			</div>
		</section>
	);
}

function escapeForSimpleHtml(s: string): string {
	return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** One <p> per line so line breaks from the composer are preserved in the thread. */
function formatPlainAsHtml(text: string): string {
	return text
		.split("\n")
		.map((line) => `<p>${escapeForSimpleHtml(line)}</p>`)
		.join("");
}
