import type { PortalComment } from "../types/portal";

export function portalCommentAnchorId(comment: Pick<PortalComment, "name">): string | undefined {
	const name = String(comment.name ?? "").trim();
	if (!name) return undefined;
	return `portal-comment-${encodeURIComponent(name)}`;
}
