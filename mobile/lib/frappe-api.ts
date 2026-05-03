/**
 * Frappe / Printechs Support portal API client.
 * Supports API Key + Secret (Authorization: token …) or session cookie + CSRF.
 */
import { getFrappeBaseUrl } from '@/lib/config';
import { clearAuth, loadAuth, saveSessionAuth, saveTokenAuth, type StoredAuth } from '@/lib/session';

const METHOD_PREFIX = '/api/method/';

function sanitizeExc(exc: string): string {
	return exc.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() || exc;
}

function joinSetCookie(headers: Headers): string | null {
	const anyHeaders = headers as Headers & { getSetCookie?: () => string[] };
	if (typeof anyHeaders.getSetCookie === 'function') {
		const parts = anyHeaders.getSetCookie();
		if (parts?.length) return parts.join('; ');
	}
	const single = headers.get('set-cookie');
	return single || null;
}

export async function callMethod<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
	const auth = await loadAuth();
	const baseUrl = auth?.baseUrl || getFrappeBaseUrl();
	if (!baseUrl) {
		throw new Error('Configure your site URL in Settings.');
	}

	const url = `${baseUrl}${METHOD_PREFIX}${encodeURIComponent(method)}`;
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		Accept: 'application/json',
	};

	if (auth?.kind === 'token') {
		headers.Authorization = `token ${auth.apiKey}:${auth.apiSecret}`;
	} else if (auth?.kind === 'session') {
		headers.Cookie = auth.cookieHeader;
		headers['X-Frappe-CSRF-Token'] = auth.csrfToken;
	}

	const res = await fetch(url, {
		method: 'POST',
		headers,
		body: JSON.stringify(args),
	});

	let data: { message?: T; exc?: string; exception?: string };
	try {
		data = (await res.json()) as typeof data;
	} catch {
		throw new Error(`HTTP ${res.status}: invalid JSON`);
	}

	if (res.status === 403 || res.status === 401) {
		await clearAuth();
		throw new Error('Session expired. Sign in again.');
	}

	if (!res.ok) {
		const raw =
			(typeof data === 'object' && data && 'message' in data && typeof data.message === 'string'
				? data.message
				: null) ||
			data.exc ||
			`HTTP ${res.status}`;
		throw new Error(sanitizeExc(String(raw)));
	}
	if (data.exc) {
		throw new Error(sanitizeExc(data.exc));
	}
	return data.message as T;
}

/** Password login via Frappe /api/method/login, then CSRF from portal helper. */
export async function loginWithPassword(baseUrl: string, usr: string, pwd: string): Promise<void> {
	const clean = baseUrl.replace(/\/$/, '');
	const loginUrl = `${clean}/api/method/login`;
	const res = await fetch(loginUrl, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'application/json',
		},
		body: JSON.stringify({ usr: usr.trim(), pwd }),
	});

	const body = await res.json().catch(() => ({}));
	if (!res.ok) {
		const msg =
			(body as { message?: string; exc?: string }).exc ||
			(body as { message?: string }).message ||
			`HTTP ${res.status}`;
		throw new Error(sanitizeExc(String(msg)));
	}

	const setCookie = joinSetCookie(res.headers);
	if (!setCookie) {
		throw new Error(
			'Login succeeded but no session cookie was returned (common on some devices). Use API Key + Secret from User → API Access in Desk, in the More tab.',
		);
	}

	const csrfUrl = `${clean}${METHOD_PREFIX}printechs_support.printechs_support_system.api.portal_api.get_portal_csrf_token`;
	const csrfRes = await fetch(csrfUrl, {
		method: 'GET',
		headers: { Accept: 'application/json', Cookie: setCookie },
	});
	const csrfData = (await csrfRes.json()) as { message?: string; exc?: string };
	if (!csrfRes.ok || !csrfData.message) {
		throw new Error(
			csrfData.exc ||
				'Could not complete session. Try API Key login, or open the site in a browser to verify your account.',
		);
	}

	await saveSessionAuth(clean, setCookie, csrfData.message);
}

export async function loginWithApiKey(baseUrl: string, apiKey: string, apiSecret: string): Promise<void> {
	const clean = baseUrl.replace(/\/$/, '');
	await saveTokenAuth(clean, apiKey.trim(), apiSecret.trim());
	// verify
	await callMethod('printechs_support.printechs_support_system.api.portal_api.get_portal_bootstrap');
}

export { clearAuth, loadAuth };
