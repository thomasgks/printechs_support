import { getFrappeSiteOrigin, portalTaskPath, portalTicketPath } from "../api";

const PORTAL_BASENAME = import.meta.env.DEV ? "" : "/support-portal";

/** Absolute path for raw `<a href>` (includes `/support-portal` when embedded). */
export function portalHrefAbsolute(spaPath: string): string {
	const p = spaPath.startsWith("/") ? spaPath : `/${spaPath}`;
	return `${PORTAL_BASENAME}${p}`;
}

/**
 * If `href` points at Desk for Support Task / Support Ticket on this bench, return the portal path
 * (same origin as the SPA). Otherwise return null.
 */
export function deskHrefToPortalHref(href: string): string | null {
	const t = href.trim();
	if (!t || t.startsWith("#") || t.toLowerCase().startsWith("mailto:") || t.toLowerCase().startsWith("javascript:")) {
		return null;
	}
	let url: URL;
	try {
		url = new URL(t, typeof window !== "undefined" ? window.location.href : "http://localhost");
	} catch {
		return null;
	}
	if (typeof window === "undefined") {
		return null;
	}
	const origins = new Set<string>([window.location.origin]);
	try {
		origins.add(getFrappeSiteOrigin());
	} catch {
		/* ignore */
	}
	if (!origins.has(url.origin)) {
		return null;
	}
	const path = url.pathname;
	const dec = (s: string) => {
		try {
			return decodeURIComponent(s);
		} catch {
			return s;
		}
	};
	let m = path.match(/\/app\/support-task\/([^/?#]+)/i);
	if (m) {
		return portalHrefAbsolute(portalTaskPath(dec(m[1])));
	}
	m = path.match(/\/app\/support-ticket\/([^/?#]+)/i);
	if (m) {
		return portalHrefAbsolute(portalTicketPath(dec(m[1])));
	}
	m = path.match(/\/app\/[^/]*\/Support%20Task\/([^/?#]+)/i);
	if (m) {
		return portalHrefAbsolute(portalTaskPath(dec(m[1])));
	}
	m = path.match(/\/app\/[^/]*\/Support%20Ticket\/([^/?#]+)/i);
	if (m) {
		return portalHrefAbsolute(portalTicketPath(dec(m[1])));
	}
	return null;
}

/**
 * Rewrite Desk doc links inside Frappe HTML (comments) so they stay in the portal SPA.
 */
export function rewriteDeskHtmlLinks(html: string): string {
	if (!html || typeof window === "undefined" || typeof DOMParser === "undefined") {
		return html;
	}
	const wrapped = `<div data-portal-root="1">${html}</div>`;
	const doc = new DOMParser().parseFromString(wrapped, "text/html");
	const root = doc.querySelector("[data-portal-root]");
	if (!root) {
		return html;
	}
	for (const a of root.querySelectorAll("a[href]")) {
		const href = a.getAttribute("href");
		if (!href) {
			continue;
		}
		const next = deskHrefToPortalHref(href);
		if (next !== null) {
			a.setAttribute("href", next);
		}
	}
	return root.innerHTML;
}
